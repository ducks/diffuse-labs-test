"""Dataset API, preview worker, identity broker, and scheduled reporting."""
import contextlib
import hashlib
import http.server
import json
import logging
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request


API_SCHEMA = '''
CREATE TABLE datasets (id TEXT PRIMARY KEY, owner TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE jobs (id TEXT PRIMARY KEY, owner TEXT NOT NULL, body TEXT NOT NULL, state TEXT NOT NULL, result TEXT, completions INTEGER NOT NULL DEFAULT 0, receipt TEXT);
CREATE TABLE schedules (id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL, dataset TEXT NOT NULL, active INTEGER NOT NULL, runs INTEGER NOT NULL DEFAULT 0);
CREATE TABLE exports (sequence INTEGER PRIMARY KEY AUTOINCREMENT, schedule TEXT NOT NULL, dataset TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE reports (sequence INTEGER PRIMARY KEY AUTOINCREMENT, schedule TEXT NOT NULL, dataset_count INTEGER NOT NULL);
CREATE TABLE audit (sequence INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, actor TEXT NOT NULL, target TEXT NOT NULL, body TEXT NOT NULL);
'''
IDENTITY_SCHEMA = '''
CREATE TABLE credentials (id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL, principal TEXT NOT NULL, kind TEXT NOT NULL, active INTEGER NOT NULL);
CREATE TABLE sessions (sequence INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, credential TEXT NOT NULL);
'''


OUTPUT_SCHEMA = """
CREATE TABLE receipts (sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, job TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE idempotency (key TEXT PRIMARY KEY, receipt TEXT NOT NULL);
CREATE TABLE publish_audit (sequence INTEGER PRIMARY KEY AUTOINCREMENT, receipt TEXT NOT NULL, job TEXT NOT NULL, body TEXT NOT NULL);
"""


@contextlib.contextmanager
def database(path):
    db = sqlite3.connect(path, timeout=10)
    try:
        with db:
            yield db
    finally:
        db.close()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def issue(db, principal, kind):
    token = secrets.token_hex(32)
    identity = secrets.token_hex(16)
    db.execute('INSERT INTO credentials VALUES (?, ?, ?, ?, 1)', (identity,digest(token),principal,kind))
    return token


def principal(db, token, kind='access'):
    row = db.execute('SELECT principal FROM credentials WHERE digest=? AND kind=? AND active=1',(digest(token),kind)).fetchone()
    return row[0] if row else None


def call(base, path, body=None, token=None, idempotency=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {'Content-Type':'application/json'}
    if token:
        headers['Authorization'] = 'Bearer '+token
    if idempotency:
        headers['Idempotency-Key'] = idempotency
    request = urllib.request.Request(base+path,data=data,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=5) as response:
            return response.status,json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code,json.loads(error.read())


def audit(db, kind, actor, target, body):
    db.execute('INSERT INTO audit(kind,actor,target,body) VALUES (?,?,?,?)',(kind,actor,target,json.dumps(body,sort_keys=True)))


def load_input(manifest, inputs, allowed):
    candidate = Path(manifest['path'])
    if not candidate.is_absolute():
        candidate = Path(inputs)/candidate
    candidate = candidate.resolve(strict=True)
    if not candidate.is_relative_to(Path(inputs).resolve(strict=True)):
        raise PermissionError('input is outside the configured data root')
    if not candidate.is_file() or candidate.stat().st_size > 1024*1024:
        raise ValueError('input must be a file under 1 MiB')
    return candidate.read_bytes()


def preview_result(data):
    return {'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'rows':len(data.splitlines())}


def server(role, port, settings):
    class Handler(http.server.BaseHTTPRequestHandler):
        def respond(self, status, payload):
            data = json.dumps(payload,sort_keys=True).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def token(self):
            header = self.headers.get('Authorization','')
            return header[7:] if header.startswith('Bearer ') else ''

        def actor(self):
            status, result = call(settings['IDENTITY_URL'],'/validate',{'token':self.token()})
            return result.get('principal') if status == 200 else None

        def handle_request(self, method):
            if self.path == '/health' and method == 'GET':
                return self.respond(200,{'status':'ok'})
            length = int(self.headers.get('Content-Length','0'))
            if not 0 <= length <= 1024*1024:
                return self.respond(413,{'error':'request too large'})
            payload = json.loads(self.rfile.read(length)) if length else {}
            if role == 'identity':
                with database(settings['DATABASE']) as db:
                    if self.path == '/validate' and method == 'POST':
                        actor = principal(db,payload.get('token',''))
                        return self.respond(200,{'principal':actor}) if actor else self.respond(401,{'error':'invalid credential'})
                    if self.path == '/refresh' and method == 'POST':
                        actor = principal(db,payload.get('refresh',''),'refresh')
                        if actor is None:
                            return self.respond(401,{'error':'invalid refresh credential'})
                        token = issue(db,actor,'access')
                        db.execute('INSERT INTO sessions(action,credential) VALUES (?,?)',('refresh',digest(payload['refresh'])))
                        db.commit()
                        return self.respond(200,{'access':token})
                return self.respond(404,{'error':'not found'})
            if role == 'worker':
                if self.path == '/preview' and method == 'POST':
                    try:
                        data = load_input(payload,settings['INPUT_DIR'],settings['ALLOWED_ROOT'])
                        return self.respond(200,{'preview':data.decode()})
                    except PermissionError:
                        return self.respond(403,{'error':'input not allowed'})
                    except (OSError,ValueError):
                        return self.respond(400,{'error':'invalid input'})
                return self.respond(404,{'error':'not found'})
            actor = self.actor()
            if actor is None:
                return self.respond(401,{'error':'invalid credential'})
            if role == 'output':
                if actor != 'worker':
                    return self.respond(403,{'error':'not allowed'})
                identity = self.path.rsplit('/',1)[-1]
                with database(settings['DATABASE']) as db:
                    if self.path.startswith('/receipts/') and method == 'GET':
                        rows = db.execute('SELECT id,body FROM receipts WHERE job=? ORDER BY sequence',(identity,)).fetchall()
                        return self.respond(200,{'receipts':[{'id':row[0],'result':json.loads(row[1])} for row in rows]})
                    if self.path.startswith('/publish/') and method == 'POST':
                        body = json.dumps(payload,sort_keys=True)
                        key = self.headers.get('Idempotency-Key')
                        db.execute('BEGIN IMMEDIATE')
                        if key:
                            old = db.execute('SELECT r.id,r.job,r.body FROM idempotency k JOIN receipts r ON r.id=k.receipt WHERE k.key=?',(key,)).fetchone()
                            if old:
                                if old[1] != identity or old[2] != body:
                                    return self.respond(409,{'error':'idempotency conflict'})
                                return self.respond(200,{'receipt':old[0]})
                        receipt = secrets.token_hex(16)
                        db.execute('INSERT INTO receipts(id,job,body) VALUES (?,?,?)',(receipt,identity,body))
                        db.execute('INSERT INTO publish_audit(receipt,job,body) VALUES (?,?,?)',(receipt,identity,body))
                        if key:
                            db.execute('INSERT INTO idempotency VALUES (?,?)',(key,receipt))
                        db.commit()
                        return self.respond(201,{'receipt':receipt})
                return self.respond(404,{'error':'not found'})
            identity = self.path.rsplit('/',1)[-1]
            with database(settings['DATABASE']) as db:
                if self.path.startswith('/datasets/') and method == 'GET':
                    row = db.execute('SELECT owner,body FROM datasets WHERE id=?',(identity,)).fetchone()
                    if row is None:
                        return self.respond(404,{'error':'not found'})
                    if actor != 'worker' and row[0] != actor:
                        return self.respond(403,{'error':'not allowed'})
                    audit(db,'dataset-read',actor,identity,{})
                    db.commit()
                    return self.respond(200,{'body':row[1]})
                if self.path.startswith('/jobs/'):
                    old = db.execute('SELECT owner,body,state,result,receipt FROM jobs WHERE id=?',(identity,)).fetchone()
                    if old and actor not in (old[0],'worker'):
                        return self.respond(403,{'error':'not allowed'})
                    if method == 'GET':
                        return self.respond(200,{'state':old[2],'result':json.loads(old[3]) if old[3] else None,'receipt':old[4]}) if old else self.respond(404,{'error':'not found'})
                    if method == 'POST' and actor.startswith('client-'):
                        if not isinstance(payload.get('path'),str):
                            return self.respond(400,{'error':'path required'})
                        body = json.dumps(payload,sort_keys=True)
                        if old and old[1] != body:
                            return self.respond(409,{'error':'conflict'})
                        if not old:
                            db.execute('INSERT INTO jobs(id,owner,body,state) VALUES (?,?,?,?)',(identity,actor,body,'queued'))
                            audit(db,'job-accepted',actor,identity,payload)
                        db.commit()
                        return self.respond(202,{'status':'accepted'})
                if self.path == '/internal/next' and method == 'GET' and actor == 'worker':
                    row = db.execute("SELECT id,body FROM jobs WHERE state='queued' ORDER BY rowid LIMIT 1").fetchone()
                    return self.respond(200,{'job':{'id':row[0],'body':json.loads(row[1])} if row else None})
                if self.path == '/internal/recovery' and method == 'GET' and actor == 'worker':
                    row = db.execute("SELECT id,body FROM jobs WHERE state='retry' ORDER BY rowid LIMIT 1").fetchone()
                    return self.respond(200,{'job':{'id':row[0],'body':json.loads(row[1])} if row else None})
                if self.path.startswith('/internal/complete/') and method == 'POST' and actor == 'worker':
                    row = db.execute('SELECT state,result,receipt FROM jobs WHERE id=?',(identity,)).fetchone()
                    if not row:
                        return self.respond(404,{'error':'not found'})
                    result = json.dumps(payload['preview'],sort_keys=True)
                    receipt = payload['receipt']
                    if not isinstance(receipt,str):
                        return self.respond(400,{'error':'receipt required'})
                    if row[0] == 'complete' and (row[1] != result or row[2] != receipt):
                        return self.respond(409,{'error':'conflict'})
                    if row[0] != 'complete':
                        db.execute("UPDATE jobs SET state='complete',result=?,receipt=?,completions=completions+1 WHERE id=?",(result,receipt,identity))
                        audit(db,'job-completed',actor,identity,payload)
                    db.commit()
                    return self.respond(200,{'status':'complete'})
                if self.path.startswith('/schedules/') and method == 'POST' and actor == 'worker':
                    target = payload.get('dataset')
                    if not db.execute('SELECT id FROM datasets WHERE id=?',(target,)).fetchone():
                        return self.respond(404,{'error':'not found'})
                    db.execute('INSERT INTO schedules VALUES (?,?,?,?,1,0)',(identity,actor,'dataset-export',target))
                    audit(db,'schedule-created',actor,identity,payload)
                    db.commit()
                    return self.respond(201,{'status':'scheduled'})
            return self.respond(403,{'error':'not allowed'})

        def dispatch(self, method):
            try:
                self.handle_request(method)
            except (ValueError,KeyError,TypeError):
                self.respond(400,{'error':'invalid request'})
            except (OSError,sqlite3.Error) as error:
                logging.warning('request processing: %s',error)
                self.respond(503,{'error':'service unavailable'})

        def do_GET(self):
            self.dispatch('GET')

        def do_POST(self):
            self.dispatch('POST')

    return http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler)


def process_one(settings):
    token = json.loads(Path(settings['ACCESS_FILE']).read_text())['access']
    # Recovery is a queue too: a committed output can outlive its worker.
    job = None
    for endpoint in ('/internal/recovery', '/internal/next'):
        status, result = call(settings['API_URL'], endpoint, token=token)
        if status != 200:
            raise RuntimeError('job authorization failed: HTTP '+str(status))
        if result['job'] is not None:
            job = result['job']
            break
    if job is None:
        return False
    data = load_input(job['body'],settings['INPUT_DIR'],settings['ALLOWED_ROOT'])
    preview = preview_result(data)
    status, existing = call(settings['OUTPUT_URL'], '/receipts/'+job['id'], token=token)
    if status != 200:
        raise RuntimeError('receipt lookup failed: HTTP '+str(status))
    receipts = existing['receipts']
    if receipts:
        # Never repeat an external effect merely because its queue ack failed.
        if len(receipts) != 1 or receipts[0]['result'] != preview:
            raise RuntimeError('durable output does not uniquely match job '+job['id'])
        receipt = receipts[0]['id']
    else:
        status, published = call(settings['OUTPUT_URL'], '/publish/'+job['id'],
                                 preview, token, idempotency='dataset-preview:'+job['id'])
        if status not in (200, 201):
            raise RuntimeError('output publication failed: HTTP '+str(status))
        receipt = published['receipt']
    status,_ = call(settings['API_URL'],'/internal/complete/'+job['id'],
                    {'preview':preview,'receipt':receipt},token)
    if status != 200:
        raise RuntimeError('completion authorization failed: HTTP '+str(status))
    return True


def processing(settings, stop):
    while not stop.is_set():
        if settings['PAUSED'] != '1':
            try:
                if process_one(settings):
                    continue
            except (OSError,ValueError,KeyError,RuntimeError) as error:
                logging.warning('preview processing: %s',error)
        stop.wait(.2)


def tick(path):
    with database(path) as db:
        for identity,owner,kind,target in db.execute('SELECT id,owner,kind,dataset FROM schedules WHERE active=1').fetchall():
            if kind == 'dataset-export':
                row = db.execute('SELECT body FROM datasets WHERE id=?',(target,)).fetchone()
                if row:
                    db.execute('INSERT INTO exports(schedule,dataset,body) VALUES (?,?,?)',(identity,target,row[0]))
            elif kind == 'digest-report':
                count = db.execute('SELECT COUNT(*) FROM datasets').fetchone()[0]
                db.execute('INSERT INTO reports(schedule,dataset_count) VALUES (?,?)',(identity,count))
            db.execute('UPDATE schedules SET runs=runs+1 WHERE id=?',(identity,))


def main():
    logging.basicConfig(level=logging.INFO)
    role = sys.argv[1]
    settings = dict(os.environ)
    if role == 'scheduler':
        while True:
            tick(settings['DATABASE'])
            time.sleep(1)
    if role == 'worker':
        stop = threading.Event()
        threading.Thread(target=processing,args=(settings,stop),daemon=True).start()
    server(role,int(settings['PORT']),settings).serve_forever()


if __name__ == '__main__':
    main()

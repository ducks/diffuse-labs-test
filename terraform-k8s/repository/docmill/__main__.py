"""Development and production entry points; deployments supply the environment."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import psycopg
import redis


def database():
    return psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=2)


def queue():
    return redis.Redis.from_url(os.environ['REDIS_URL'], socket_timeout=1,
                               socket_connect_timeout=1, decode_responses=True)


def storage():
    return Path(os.environ['DOCMILL_STORAGE'])


def token():
    value = Path(os.environ['DOCMILL_TOKEN_FILE']).read_text().strip()
    if not value:
        raise ValueError('empty API token')
    return value


def migrate():
    with database() as db:
        db.execute(Path(__file__).with_name('schema.sql').read_text())


def process_one():
    # Redis is a wake-up queue. PostgreSQL owns accepted work, including work
    # whose wake-up signal disappears during a cache restart.
    try:
        hint = queue().rpop('docmill:pending')
    except redis.RedisError:
        hint = None
    with database() as db:
        row = None
        if hint:
            row = db.execute("SELECT id,label FROM reports WHERE id=%s AND state='queued' FOR UPDATE SKIP LOCKED", (hint,)).fetchone()
        if row is None:
            row = db.execute("SELECT id,label FROM reports WHERE state='queued' ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED").fetchone()
        if row is None:
            return False
        identity, label = row
        # A real external renderer is intentionally part of the application's
        # runtime dependency graph, not just its Python dependency list.
        graph = 'digraph report { source [label=' + json.dumps(label) + ']; result [label="Report ready"]; source -> result; }'
        rendered = subprocess.run(['dot', '-Tsvg'], input=graph.encode(),
                                  capture_output=True, check=True, timeout=10).stdout
        if len(rendered) > 1024 * 1024:
            raise ValueError('unexpectedly large report')
        destination = storage() / (identity + '.svg')
        staged = destination.with_suffix('.tmp')
        with staged.open('wb') as output:
            output.write(rendered)
            output.flush()
            os.fsync(output.fileno())
        os.replace(staged, destination)
        db.execute("UPDATE reports SET state='done',filename=%s,bytes=%s WHERE id=%s",
                   (destination.name, len(rendered), identity))
    logging.info('report completed: %s', identity)
    return True


def worker():
    while True:
        try:
            if process_one():
                continue
        except (psycopg.Error, redis.RedisError, OSError, subprocess.SubprocessError, ValueError):
            logging.exception('report attempt failed; durable work remains queued')
        time.sleep(.25)


def serve():
    token()  # Fail at startup if the separately provisioned credential is absent.

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, value, kind='application/json'):
            data = value if isinstance(value, bytes) else json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            supplied = self.headers.get('Authorization', '')
            return hmac.compare_digest(supplied, 'Bearer ' + token())

        def do_GET(self):
            try:
                if self.path == '/health':
                    with database() as db:
                        db.execute('SELECT count(*) FROM reports').fetchone()
                    queue().ping()
                    token()
                    if not storage().is_dir():
                        raise OSError('report storage is missing')
                    return self.respond(200, {'status': 'ready'})
                if not self.authorized():
                    return self.respond(401, {'error': 'unauthorized'})
                kind, _, identity = self.path.lstrip('/').partition('/')
                if kind not in ('jobs', 'reports') or len(identity.removesuffix('.svg')) != 32:
                    return self.respond(404, {'error': 'not found'})
                identity = identity.removesuffix('.svg')
                with database() as db:
                    row = db.execute('SELECT label,state,filename,bytes FROM reports WHERE id=%s', (identity,)).fetchone()
                if row is None:
                    return self.respond(404, {'error': 'not found'})
                if kind == 'jobs':
                    return self.respond(200, {'id': identity, 'label': row[0], 'state': row[1],
                                             'bytes': row[3]})
                if row[1] != 'done':
                    return self.respond(409, {'error': 'not ready'})
                return self.respond(200, (storage() / row[2]).read_bytes(), 'image/svg+xml')
            except (psycopg.Error, redis.RedisError, OSError, ValueError):
                self.respond(503, {'error': 'dependency unavailable'})

        def do_POST(self):
            try:
                if not self.authorized():
                    return self.respond(401, {'error': 'unauthorized'})
                if self.path != '/jobs':
                    return self.respond(404, {'error': 'not found'})
                size = int(self.headers.get('Content-Length', '0'))
                if not 1 <= size <= 4096:
                    return self.respond(400, {'error': 'invalid request size'})
                label = json.loads(self.rfile.read(size))['label']
                if not isinstance(label, str) or not 1 <= len(label) <= 80:
                    return self.respond(400, {'error': 'label must contain 1-80 characters'})
                identity = uuid.uuid4().hex
                with database() as db:
                    db.execute('INSERT INTO reports(id,label) VALUES (%s,%s)', (identity, label))
                try:
                    queue().lpush('docmill:pending', identity)
                except redis.RedisError:
                    logging.warning('wake-up enqueue unavailable; durable work will be polled')
                self.respond(202, {'id': identity})
            except (ValueError, KeyError, TypeError):
                self.respond(400, {'error': 'invalid request'})
            except (psycopg.Error, redis.RedisError, OSError):
                self.respond(503, {'error': 'dependency unavailable'})

    ThreadingHTTPServer((os.environ.get('DOCMILL_BIND', '127.0.0.1'),
                         int(os.environ.get('DOCMILL_PORT', '8080'))), Handler).serve_forever()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    {'migrate': migrate, 'api': serve, 'worker': worker}[sys.argv[1]]()

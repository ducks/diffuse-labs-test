"""Initialize a dataset platform deployment without overwriting retained state."""
import json
import os
from pathlib import Path
import pwd
import secrets
import sqlite3
import sys

from platform_service import API_SCHEMA, IDENTITY_SCHEMA, OUTPUT_SCHEMA, audit, database, issue, preview_result


def initialize(root):
    def path(value):
        return root/value.lstrip('/')

    for name in ('dataset-api','dataset-identity','dataset-worker','dataset-output'):
        path('/var/lib/'+name).mkdir(parents=True,exist_ok=True)
    path('/var/lib/dataset-worker/incoming').mkdir(exist_ok=True)
    path('/etc/dataset-platform').mkdir(parents=True,exist_ok=True)
    identity_path = path('/var/lib/dataset-identity/auth.sqlite3')
    api_path = path('/var/lib/dataset-api/state.sqlite3')
    output_path = path('/var/lib/dataset-output/receipts.sqlite3')
    credentials = path('/var/lib/dataset-worker/identity.json')
    client_profile = path('/etc/dataset-platform/client.json')
    if not identity_path.exists():
        with database(identity_path) as db:
            db.executescript(IDENTITY_SCHEMA)
            db.execute('PRAGMA journal_mode=WAL')
            worker = {'access':issue(db,'worker','access'),'refresh':issue(db,'worker','refresh')}
            client = issue(db,'client-a','access')
        credentials.write_text(json.dumps(worker)+'\n')
        credentials.chmod(0o600)
        client_profile.write_text(json.dumps({'access':client})+'\n')
        client_profile.chmod(0o600)
    if not output_path.exists():
        with database(output_path) as db:
            db.executescript(OUTPUT_SCHEMA)
            db.execute('PRAGMA journal_mode=WAL')
    if not api_path.exists():
        public_id,private_id,job_id,schedule_id = [secrets.token_hex(16) for _ in range(4)]
        content = 'name,value\n'+secrets.token_hex(12)+',17\n'
        path('/var/lib/dataset-worker/incoming/archive.csv').write_text(content)
        with database(api_path) as db:
            db.executescript(API_SCHEMA)
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('INSERT INTO datasets VALUES (?,?,?)',(public_id,'client-a',secrets.token_hex(48)))
            db.execute('INSERT INTO datasets VALUES (?,?,?)',(private_id,'client-b',secrets.token_hex(48)))
            body = {'path':'archive.csv'}
            result = preview_result(content.encode())
            receipt = secrets.token_hex(16)
            with database(output_path) as output:
                output.execute('INSERT INTO receipts(id,job,body) VALUES (?,?,?)',(receipt,job_id,json.dumps(result,sort_keys=True)))
                output.execute('INSERT INTO publish_audit(receipt,job,body) VALUES (?,?,?)',(receipt,job_id,json.dumps(result,sort_keys=True)))
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,1,?)',(job_id,'client-a',json.dumps(body,sort_keys=True),'complete',json.dumps(result,sort_keys=True),receipt))
            db.execute('INSERT INTO schedules VALUES (?,?,?,?,1,0)',(schedule_id,'reports','digest-report',public_id))
            audit(db,'job-completed','worker',job_id,result)
        profile = json.loads(client_profile.read_text())
        profile['dataset'] = public_id
        client_profile.write_text(json.dumps(profile)+'\n')
    configurations = {
        'identity.env':{'PORT':'9101','DATABASE':'/var/lib/dataset-identity/auth.sqlite3'},
        'api.env':{'PORT':'9100','DATABASE':'/var/lib/dataset-api/state.sqlite3','IDENTITY_URL':'http://127.0.0.1:9101'},
        'worker.env':{'PORT':'9102','API_URL':'http://127.0.0.1:9100','ACCESS_FILE':'/var/lib/dataset-worker/identity.json','INPUT_DIR':'/var/lib/dataset-worker/incoming','ALLOWED_ROOT':'/','PAUSED':'0','OUTPUT_URL':'http://127.0.0.1:9103'},
        'output.env':{'PORT':'9103','DATABASE':'/var/lib/dataset-output/receipts.sqlite3','IDENTITY_URL':'http://127.0.0.1:9101'},
        'scheduler.env':{'DATABASE':'/var/lib/dataset-api/state.sqlite3'},
    }
    for name,settings in configurations.items():
        target = path('/etc/dataset-platform/'+name)
        if not target.exists():
            target.write_text(''.join(key+'='+value+'\n' for key,value in settings.items()))
            target.chmod(0o644)
    if root == Path('/') and os.geteuid() == 0:
        for name in ('dataset-api','dataset-identity','dataset-worker','dataset-output'):
            user = pwd.getpwnam(name)
            directory = path('/var/lib/'+name)
            for target in [directory,*directory.rglob('*')]:
                os.chown(target,user.pw_uid,user.pw_gid)
            directory.chmod(0o750)


if __name__ == '__main__':
    initialize(Path('/'))

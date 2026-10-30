"""Controller-only containment probes and independent retained-state checks."""
import contextlib
import hashlib
import inspect
import json
import os
from pathlib import Path
import pwd
import secrets
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

import traffic


class Failure(RuntimeError):
    def __init__(self, category, message):
        super().__init__(message)
        self.category = category


def guest_action(action, data, root=Path('/')):
    def path(value):
        return root/value.lstrip('/')

    def snapshot():
        queries = {
            'datasets':'SELECT id,owner,body FROM datasets ORDER BY id',
            'jobs':'SELECT id,owner,body,state,result,completions,receipt FROM jobs ORDER BY id',
            'schedules':'SELECT id,owner,kind,dataset,active,runs FROM schedules ORDER BY id',
            'exports':'SELECT sequence,schedule,dataset,body FROM exports ORDER BY sequence',
            'reports':'SELECT sequence,schedule,dataset_count FROM reports ORDER BY sequence',
            'audit':'SELECT sequence,kind,actor,target,body FROM audit ORDER BY sequence',
        }
        with contextlib.closing(sqlite3.connect('file:'+str(path('/var/lib/dataset-api/state.sqlite3'))+'?mode=ro',uri=True)) as db:
            result = {name:db.execute(query).fetchall() for name,query in queries.items()}
        with contextlib.closing(sqlite3.connect('file:'+str(path('/var/lib/dataset-identity/auth.sqlite3'))+'?mode=ro',uri=True)) as db:
            result['credentials'] = db.execute('SELECT id,digest,principal,kind,active FROM credentials ORDER BY id').fetchall()
            result['identity_sessions'] = db.execute('SELECT sequence,action,credential FROM sessions ORDER BY sequence').fetchall()
        with contextlib.closing(sqlite3.connect('file:'+str(path('/var/lib/dataset-output/receipts.sqlite3'))+'?mode=ro',uri=True)) as db:
            result['receipts'] = db.execute('SELECT sequence,id,job,body FROM receipts ORDER BY sequence').fetchall()
            result['publish_audit'] = db.execute('SELECT sequence,receipt,job,body FROM publish_audit ORDER BY sequence').fetchall()
        return result

    if action == 'snapshot':
        return snapshot()
    if action == 'bootstrap':
        result = snapshot()
        result['client'] = json.loads(path('/etc/dataset-platform/client.json').read_text())
        result['identity_path'] = str(path('/var/lib/dataset-worker/identity.json'))
        return result
    if action == 'partial':
        # Publish and commit the external effect before exposing the retry row.
        # The active worker cannot race this fixture and publish it first.
        output_path = path('/var/lib/dataset-output/receipts.sqlite3')
        api_path = path('/var/lib/dataset-api/state.sqlite3')
        for identity,record in data.items():
            receipt = secrets.token_hex(16)
            body = json.dumps(record['result'],sort_keys=True)
            with contextlib.closing(sqlite3.connect(output_path,timeout=10)) as db:
                with db:
                    db.execute('INSERT INTO receipts(id,job,body) VALUES (?,?,?)',(receipt,identity,body))
                    db.execute('INSERT INTO publish_audit(receipt,job,body) VALUES (?,?,?)',(receipt,identity,body))
            with contextlib.closing(sqlite3.connect(api_path,timeout=10)) as db:
                with db:
                    payload = json.dumps(record['body'],sort_keys=True)
                    db.execute('INSERT INTO jobs(id,owner,body,state) VALUES (?,?,?,?)',(identity,'client-a',payload,'retry'))
                    db.execute('INSERT INTO audit(kind,actor,target,body) VALUES (?,?,?,?)',('job-accepted','client-a',identity,payload))
        # SQLite may keep WAL files open across another service's read. Restore
        # their database owner's permissions after this controller observation.
        if root == Path('/'):
            for database_path in (output_path,api_path):
                owner = database_path.stat()
                for filename in (database_path,Path(str(database_path)+'-wal'),Path(str(database_path)+'-shm')):
                    if filename.exists():
                        os.chown(filename,owner.st_uid,owner.st_gid)
        return {'created':len(data)}
    if action in ('inputs','probes'):
        incoming = path('/var/lib/dataset-worker/incoming')
        if action == 'inputs':
            files = {incoming/(identity+'.csv'):text for identity,text in data.items()}
            returned = {identity:{'path':identity+'.csv'} for identity in data}
        else:
            identity = data['id']
            outside = path('/var/lib/dataset-worker/external')/(identity+'.txt')
            sibling = path('/var/lib/dataset-worker/incoming-archive')/(identity+'.txt')
            files = {outside:data['content'],sibling:data['content']}
            link = incoming/(identity+'.link')
            link.symlink_to(outside)
            returned = [str(outside),str(sibling),str(incoming/'..'/'external'/outside.name),str(link)]
        for filename,text in files.items():
            filename.parent.mkdir(parents=True,exist_ok=True)
            filename.write_text(text)
            filename.chmod(0o644)
            if root == Path('/'):
                user = pwd.getpwnam('dataset-worker')
                os.chown(filename,user.pw_uid,user.pw_gid)
        return returned
    raise ValueError('unknown guest observation')


def remote(action, data=None):
    port = int(os.environ['REPLAYBOOK_HOST_SSH_PORT'])
    if not 0 < port < 65536:
        raise ValueError('invalid SSH port')
    key = os.environ.get('REPLAYBOOK_HOST_SSH_KEY',str(Path.home()/'.ssh/id_ed25519'))
    source = 'import contextlib,json,os,pathlib,pwd,secrets,sqlite3\nfrom pathlib import Path\n'
    source += inspect.getsource(guest_action)
    source += '\nprint(json.dumps(guest_action('+repr(action)+','+repr(data or {})+')))\n'
    result = subprocess.run(['ssh','-i',key,'-p',str(port),'-o','BatchMode=yes',
        '-o','ConnectTimeout=5','-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/dev/null',
        '-o','LogLevel=ERROR','root@127.0.0.1','python -'],input=source,text=True,
        capture_output=True,timeout=25,check=True)
    return json.loads(result.stdout)


def request(base, path, payload=None, token=None, timeout=6):
    headers = {'Content-Type':'application/json'}
    if token:
        headers['Authorization'] = 'Bearer '+token
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base+path,data=data,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:
            return response.status,json.loads(response.read())
    except urllib.error.HTTPError as error:
        body = error.read()
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = {'error':'non-JSON HTTP error'}
        return error.code,parsed


def require(condition, category, message):
    if not condition:
        raise Failure(category,message)


def http(base,path,payload=None,token=None,status=200):
    observed,result = request(base,path,payload,token)
    require(observed == status,'http_contract_failed',f'{path}: HTTP {observed}; required {status}')
    return result


def wait_ready(base):
    end = time.monotonic()+60
    while True:
        try:
            for path in ('/health','/identity/health','/worker/health','/outputs/health'):
                require(http(base,path).get('status')=='ok','service_not_ready','control path is not ready')
            return
        except (Failure,OSError):
            if time.monotonic() >= end:
                raise
            time.sleep(.2)


def hash_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def new_work(base, client, count=4):
    files = {secrets.token_hex(16):'name,value\n'+secrets.token_hex(24)+','+str(secrets.randbelow(10000))+'\n' for _ in range(count)}
    manifests = remote('inputs',files)
    records = {}
    for identity,payload in manifests.items():
        http(base,'/api/jobs/'+identity,payload,client['access'],202)
        content = files[identity]
        records[identity] = {'body':payload,'result':{'sha256':hash_text(content),'bytes':len(content.encode()),'rows':len(content.splitlines())}}
    return records


def interrupted_work(count=3):
    files = {secrets.token_hex(16):'name,value\n'+secrets.token_hex(24)+','+str(secrets.randbelow(10000))+'\n' for _ in range(count)}
    manifests = remote('inputs',files)
    records = {identity:{'body':manifests[identity],'result':{'sha256':hash_text(content),
                'bytes':len(content.encode()),'rows':len(content.splitlines())}}
               for identity,content in files.items()}
    remote('partial',records)
    return records


def preserve_rows(expected, observed, category):
    by_id = {row[0]:row for row in observed}
    require(all(by_id.get(row[0]) == row for row in expected),category,'retained evidence was removed or modified')


def jobs_ok(records, observed):
    jobs = {row[0]:row for row in observed['jobs']}
    for identity, expected in records.items():
        row = jobs.get(identity)
        require(row is not None,'accepted_jobs_lost','accepted preview job is missing')
        require(json.loads(row[2]) == expected['body'],'accepted_jobs_changed','accepted preview input changed')
        require(row[3] == 'complete' and row[4] is not None,'backlog_not_recovered','accepted preview is not complete')
        require(json.loads(row[4]) == expected['result'] and row[5] == 1,'preview_result_invalid','preview result changed, duplicated, or missing')


def receipts_ok(records, observed):
    jobs = {row[0]:row for row in observed['jobs']}
    for identity,record in records.items():
        receipts = [row for row in observed['receipts'] if row[2]==identity]
        events = [row for row in observed['publish_audit'] if row[2]==identity]
        require(len(receipts)==1 and len(events)==1,'output_duplicated_or_lost',
                'accepted job must have exactly one durable output and publish event')
        receipt,event = receipts[0],events[0]
        require(json.loads(receipt[3])==record['result'] and json.loads(event[3])==record['result']
                and event[1]==receipt[1], 'published_output_changed','published output contents changed')
        row = jobs.get(identity)
        require(row is not None and row[6]==receipt[1],'output_acknowledgement_missing',
                'queue acknowledgement does not reference the existing output')


def retained_ok(state, observed):
    initial = state['retained']
    for name in ('datasets','exports','audit','identity_sessions','reports','receipts','publish_audit'):
        preserve_rows(initial[name],observed[name],'retained_'+name+'_changed')
    jobs_ok(state['records'],observed)
    receipts_ok(state['records'],observed)
    schedules = {row[0]:row for row in observed['schedules']}
    legit = initial['legitimate_schedule']
    current = schedules.get(legit[0])
    require(current is not None and current[:5] == legit[:5],'legitimate_schedule_disabled','legitimate scheduled reporting was changed or disabled')
    bad = schedules.get(state['schedule'])
    require(bad is None or bad[4] == 0,'unauthorized_schedule_active','unauthorized recurring export remains active')
    exposed = set(state['exposed_digests'])
    require(not any(row[1] in exposed and row[4] for row in observed['credentials']),
            'exposed_credentials_active','an exposed access or refresh credential remains active')


def wait_jobs(state, timeout=25):
    end = time.monotonic()+timeout
    while True:
        observed = remote('snapshot')
        try:
            jobs_ok(state['records'],observed)
            receipts_ok(state['records'],observed)
            return observed
        except Failure:
            if time.monotonic() >= end:
                raise
            time.sleep(.2)


def containment_ok(base, state):
    for access in state['stolen_access']:
        status,_ = request(base,'/api/datasets/'+state['private_dataset'],token=access)
        require(status in (401,403),'exposed_access_accepted','old access credential still reads a protected dataset')
    status,_ = request(base,'/identity/refresh',{'refresh':state['stolen_refresh']})
    require(status in (401,403),'exposed_refresh_accepted','old refresh credential still issues access')
    probes = remote('probes',{'id':secrets.token_hex(16),'content':secrets.token_hex(64)})
    for path in [state['identity_path'],*probes]:
        status,_ = request(base,'/worker/preview',{'path':path})
        require(status in (400,403),'input_boundary_open','a file outside the input directory remains readable')
    client = state['client']
    result = http(base,'/api/datasets/'+client['dataset'],token=client['access'])
    require(result['body']==state['client_body'],'legitimate_client_data_changed','legitimate client dataset changed')
    status,_ = request(base,'/api/datasets/'+state['private_dataset'],token=client['access'])
    require(status==403,'tenant_boundary_open','unrelated client gained access to another tenant')
    # Normal preview loading must remain available: disabling the loader is not
    # containment. The same body is also checked in the independent job ledger.
    sample = next(iter(state['records'].values()))
    preview = http(base,'/worker/preview',sample['body']).get('preview')
    require(isinstance(preview,str) and hash_text(preview)==sample['result']['sha256']
            and len(preview.encode())==sample['result']['bytes']
            and len(preview.splitlines())==sample['result']['rows'],
            'legitimate_preview_changed','legitimate preview contents changed')


def run(phase, base, state_dir):
    state_dir.mkdir(parents=True,exist_ok=True)
    state_file = state_dir/'response-contract.json'
    wait_ready(base)
    if phase == 'preflight':
        initial = remote('bootstrap')
        client = initial.pop('client')
        identity_path = initial.pop('identity_path')
        client_row = next(row for row in initial['datasets'] if row[0] == client['dataset'])
        private = next(row for row in initial['datasets'] if row[1] != 'client-a')
        require(http(base,'/api/datasets/'+client['dataset'],token=client['access'])['body']==client_row[2],
                'incident_not_reproduced','legitimate client control path failed')
        http(base,'/api/datasets/'+private[0],token=client['access'],status=403)
        leaked = http(base,'/worker/preview',{'path':identity_path})
        stolen = json.loads(leaked['preview'])
        require(http(base,'/api/datasets/'+private[0],token=stolen['access'])['body']==private[2],
                'incident_not_reproduced','disclosed credential did not access the protected dataset')
        refreshed = http(base,'/identity/refresh',{'refresh':stolen['refresh']})['access']
        http(base,'/api/datasets/'+private[0],token=refreshed)
        schedule = secrets.token_hex(16)
        http(base,'/api/schedules/'+schedule,{'dataset':private[0]},stolen['access'],201)
        records = interrupted_work()
        end = time.monotonic()+15
        while True:
            observed = remote('snapshot')
            if any(row[1] == schedule for row in observed['exports']):
                break
            require(time.monotonic()<end,'incident_not_reproduced','recurring export did not execute')
            time.sleep(.2)
        by_id = {row[0]:row for row in observed['jobs']}
        require(all(by_id[identity][3]=='retry' for identity in records),'incident_not_reproduced','interrupted jobs did not retain their retry state')
        # Historical completed work must be retained with its original results.
        for row in initial['jobs']:
            records[row[0]] = {'body':json.loads(row[2]),'result':json.loads(row[4])}
        legit = next(row for row in observed['schedules'] if row[2]=='digest-report')
        retained = {name:observed[name] for name in ('datasets','exports','audit','identity_sessions','reports','receipts','publish_audit')}
        retained['legitimate_schedule'] = legit
        state = {'client':client,'client_body':client_row[2],'private_dataset':private[0],
                 'identity_path':identity_path,'stolen_access':[stolen['access'],refreshed],
                 'stolen_refresh':stolen['refresh'],'schedule':schedule,'records':records,
                 'retained':retained,'exposed_digests':[row[1] for row in observed['credentials'] if row[2]=='worker']}
        state_file.write_text(json.dumps(state,sort_keys=True)+'\n')
        state_file.chmod(0o600)
        traffic.start(base,state_dir)
        try:
            traffic.ready(state_dir)
        except Exception:
            traffic.stop(state_dir)
            raise
        return
    state = json.loads(state_file.read_text())
    if phase == 'immediate':
        witness = traffic.stop(state_dir)
        require(witness.get('final') and witness.get('stop_reason')=='verification',
                'live_monitor_lost','controller live-traffic witness did not finish normally')
        require(not witness['errors'],'live_traffic_failed','live client traffic failed or missed its completion deadline')
        require(witness['cycles']>=2 and witness['completed']>=1,
                'live_monitor_insufficient','live traffic baseline is missing')
        state['records'].update({identity:{'body':record['body'],'result':record['result']}
                                 for identity,record in witness['records'].items()})
        state['live_traffic'] = {key:witness[key] for key in ('cycles','completed','errors')}
        state_file.write_text(json.dumps(state,sort_keys=True)+'\n')
    wait_jobs(state)
    observed = remote('snapshot')
    retained_ok(state,observed)
    containment_ok(base,state)
    state['records'].update(interrupted_work())
    state['records'].update(new_work(base,state['client']))
    # Client retries must not create duplicate completions or mutate payloads.
    for identity,record in state['records'].items():
        http(base,'/api/jobs/'+identity,record['body'],state['client']['access'],202)
    wait_jobs(state)
    before = remote('snapshot')
    retained_ok(state,before)
    legit = state['retained']['legitimate_schedule'][0]
    before_reports = len([row for row in before['reports'] if row[1]==legit])
    end = time.monotonic()+10
    while True:
        time.sleep(.25)
        after = remote('snapshot')
        require(after['exports']==before['exports'],'unauthorized_export_continues','export activity continued after containment')
        if len([row for row in after['reports'] if row[1]==legit]) > before_reports:
            # Observe more than one scheduler interval; a single lucky gap is
            # not evidence that recurring activity has stopped.
            if time.monotonic()+1.5 < end:
                time.sleep(1.5)
                after = remote('snapshot')
                require(after['exports']==before['exports'],'unauthorized_export_continues','export activity continued after containment')
            break
        require(time.monotonic()<end,'legitimate_reporting_stalled','legitimate scheduled reporting did not progress')
    retained_ok(state,after)
    state_file.write_text(json.dumps(state,sort_keys=True)+'\n')


if __name__ == '__main__':
    phase,base,state = sys.argv[1:]
    try:
        run(phase,base,Path(state))
    except Exception as error:
        target = Path(state);target.mkdir(parents=True,exist_ok=True)
        (target/'phase-failure.json').write_text(json.dumps({'phase':phase,
            'category':getattr(error,'category','verification_failed'),'message':str(error)})+'\n')
        print(str(error),file=sys.stderr)
        sys.exit(1)

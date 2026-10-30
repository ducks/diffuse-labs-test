"""Controller-owned, bounded live traffic witness; never installed in the guest."""
import json
import os
from pathlib import Path
import secrets
import sys
import time


INTERVAL = 1.0
JOB_DEADLINE = 15.0
MAX_SECONDS = 1100.0


def write(path, value):
    temporary = path.with_name(path.name+'.'+secrets.token_hex(4)+'.tmp')
    with temporary.open('x') as stream:
        os.chmod(temporary,0o600)
        json.dump(value,stream,sort_keys=True)
        stream.write('\n')
    os.replace(temporary,path)


def identity(pid):
    try:
        fields = Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
        return fields[19] if fields[0]!='Z' else None
    except (OSError,IndexError):
        return None


def prepare(state_dir, runner_pid):
    nonce = secrets.token_hex(16)
    control = {'nonce':nonce,'runner_pid':runner_pid,'runner_identity':identity(runner_pid),
               'stop':'traffic-stop-'+nonce,'report':'traffic-report-'+nonce+'.json'}
    write(state_dir/'traffic-control.json',control)
    return control


def start(base, state_dir):
    control = prepare(state_dir,os.getppid())
    command = [sys.executable,str(Path(__file__).resolve()),base,str(state_dir),control['nonce']]
    log = state_dir/('traffic-'+control['nonce']+'.log')
    with open(os.devnull,'rb') as source,log.open('xb') as output:
        os.chmod(log,0o600)
        pid = os.posix_spawn(sys.executable,command,dict(os.environ),setsid=True,
              file_actions=[(os.POSIX_SPAWN_DUP2,source.fileno(),0),
                            (os.POSIX_SPAWN_DUP2,output.fileno(),1),
                            (os.POSIX_SPAWN_DUP2,output.fileno(),2)])
    control.update(pid=pid,identity=identity(pid))
    write(state_dir/'traffic-control.json',control)
    return control


def report(state_dir):
    control = json.loads((state_dir/'traffic-control.json').read_text())
    path = state_dir/control['report']
    return json.loads(path.read_text()) if path.exists() else None


def ready(state_dir, timeout=25):
    end = time.monotonic()+timeout
    while time.monotonic()<end:
        observed = report(state_dir)
        if observed:
            if observed['errors'] or observed['final']:
                raise RuntimeError('live traffic baseline failed')
            if observed['cycles']>=2 and observed['completed']>=1:
                return observed
        time.sleep(.1)
    raise RuntimeError('live traffic baseline did not become ready')


def stop(state_dir, timeout=25):
    control = json.loads((state_dir/'traffic-control.json').read_text())
    (state_dir/control['stop']).touch(mode=0o600,exist_ok=True)
    end = time.monotonic()+timeout
    while time.monotonic()<end:
        observed = report(state_dir)
        if observed and observed['final']:
            return observed
        time.sleep(.1)
    raise RuntimeError('live traffic witness did not stop within its bound')


def run(base, state_dir, nonce, controller=None, interval=INTERVAL,
        deadline=JOB_DEADLINE, max_seconds=MAX_SECONDS):
    if controller is None:
        import lifecycle as controller
    control = json.loads((state_dir/'traffic-control.json').read_text())
    if control['nonce']!=nonce:
        return
    state = json.loads((state_dir/'response-contract.json').read_text())
    client = state['client']
    started = time.monotonic()
    current = {'nonce':nonce,'cycles':0,'completed':0,'records':{},'errors':[],
               'final':False,'stop_reason':None}
    pending = {}
    destination = state_dir/control['report']

    def error(kind):
        if len(current['errors'])<100:
            current['errors'].append({'kind':kind,'after_seconds':round(time.monotonic()-started,3)})

    def inspect_pending():
        for job,accepted in list(pending.items()):
            record = current['records'][job]
            try:
                status,payload = controller.request(base,'/api/jobs/'+job,token=client['access'],timeout=2)
                if status==200 and payload.get('state')=='complete':
                    if payload.get('result')!=record['result'] or not payload.get('receipt'):
                        error('live-result-invalid')
                    elif time.monotonic()-accepted>deadline:
                        error('live-job-deadline')
                    else:
                        current['completed']+=1
                    record['latency_seconds']=round(time.monotonic()-accepted,3)
                    del pending[job]
                    continue
            except (OSError,ValueError):
                pass
            if time.monotonic()-accepted>deadline:
                error('live-job-deadline')
                record['deadline_missed']=True
                del pending[job]

    try:
        while True:
            active = json.loads((state_dir/'traffic-control.json').read_text())
            if active['nonce']!=nonce:
                return
            if not control['runner_identity'] or identity(control['runner_pid'])!=control['runner_identity']:
                current['stop_reason']='runner-exited'
                break
            if time.monotonic()-started>max_seconds:
                current['stop_reason']='expired'
                error('monitor-expired')
                break
            if (state_dir/control['stop']).exists():
                current['stop_reason']='verification'
                break
            current['cycles']+=1
            try:
                status,payload = controller.request(base,'/api/datasets/'+client['dataset'],token=client['access'],timeout=2)
                if status!=200 or payload.get('body')!=state['client_body']:
                    error('live-read-failed')
            except (OSError,ValueError):
                error('live-read-failed')
            job = secrets.token_hex(16)
            content = 'name,value\n'+secrets.token_hex(24)+','+str(secrets.randbelow(10000))+'\n'
            try:
                manifest = controller.remote('inputs',{job:content})[job]
                status,payload = controller.request(base,'/api/jobs/'+job,manifest,client['access'],timeout=2)
                if status!=202:
                    error('live-submit-failed')
                else:
                    accepted=time.monotonic()
                    current['records'][job]={'body':manifest,'result':{'sha256':controller.hash_text(content),
                        'bytes':len(content.encode()),'rows':len(content.splitlines())},
                        'accepted_after_seconds':round(accepted-started,3)}
                    pending[job]=accepted
            except (OSError,ValueError,KeyError):
                error('live-submit-failed')
            inspect_pending()
            write(destination,current)
            end=time.monotonic()+interval
            while time.monotonic()<end and not (state_dir/control['stop']).exists():
                time.sleep(min(.05,end-time.monotonic()))
        # Drain only already accepted work before the verifier starts its own
        # service restart/reboot. No more client requests are submitted here.
        end=time.monotonic()+deadline+2
        while pending and time.monotonic()<end:
            inspect_pending()
            write(destination,current)
            time.sleep(.1)
        if pending:
            error('live-jobs-unfinished')
    except Exception as exception:
        current['stop_reason']='monitor-error'
        error(type(exception).__name__)
    finally:
        active=json.loads((state_dir/'traffic-control.json').read_text())
        if active['nonce']==nonce:
            current['final']=True
            write(destination,current)


if __name__ == '__main__':
    base,state,nonce=sys.argv[1:]
    run(base,Path(state),nonce)

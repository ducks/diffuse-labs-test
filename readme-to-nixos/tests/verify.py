import base64
import hashlib
import json
import secrets
import shlex
import time
import xml.etree.ElementTree as ET


def run_python(machine, source, *arguments):
    return machine.succeed('python -c ' + shlex.quote(source) + ' ' +
                           ' '.join(shlex.quote(str(a)) for a in arguments))


def request(machine, host, path, token=None, body=None):
    source = '''import base64,json,sys,urllib.request,urllib.error
host,path,token,body=json.loads(sys.argv[1])
headers={}
if token is not None: headers['Authorization']='Bearer '+token
if body is not None: headers['Content-Type']='application/json'
data=None if body is None else json.dumps(body).encode()
try:
 r=urllib.request.urlopen(urllib.request.Request('http://'+host+':8080'+path,data=data,headers=headers),timeout=3)
except urllib.error.HTTPError as e: r=e
print(json.dumps({'status':r.status,'body':base64.b64encode(r.read()).decode()}))'''
    result = json.loads(run_python(machine, source, json.dumps([host, path, token, body])))
    return result['status'], base64.b64decode(result['body'])


def ready(machine):
    machine.wait_until_succeeds('curl -fsS --max-time 3 http://127.0.0.1:8080/health', timeout=90)


def provision_secret(machine, value):
    # Runtime-generated values do not appear in Nix expressions or the store.
    machine.succeed('install -d -m 0755 /run/secrets')
    source = '''import grp,os,pathlib,sys
p=pathlib.Path('/run/secrets/docmill-api')
p.write_text(sys.argv[1]+'\\n')
os.chown(p,0,grp.getgrnam('docmill').gr_gid)
p.chmod(0o640)'''
    run_python(machine, source, value)


def submit(machine, host, credential, label):
    status, body = request(machine, host, '/jobs', credential, {'label': label})
    assert status == 202, (status, body)
    identity = json.loads(body)['id']
    assert len(identity) == 32
    return identity


def finish(machine, host, credential, identity, label):
    end = time.monotonic() + 30
    while True:
        status, raw = request(machine, host, '/jobs/' + identity, credential)
        assert status == 200, (status, raw)
        job = json.loads(raw)
        assert job['id'] == identity and job['label'] == label
        if job['state'] == 'done':
            break
        assert time.monotonic() < end, 'accepted report did not complete in 30 seconds'
        time.sleep(.25)
    status, svg = request(machine, host, '/reports/' + identity + '.svg', credential)
    assert status == 200 and len(svg) == job['bytes'] and len(svg) > 200
    root = ET.fromstring(svg)
    assert root.tag.endswith('svg')
    text = ''.join(root.itertext())
    assert label in text and 'Report ready' in text
    return hashlib.sha256(svg).hexdigest()


def assert_service_users(machine):
    source = '''import json,os,pathlib
found={}
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit(): continue
 try: args=(p/'cmdline').read_bytes().decode().split('\\0')
 except (OSError,UnicodeError): continue
 args=[a for a in args if a]
 if len(args)>1 and args[-1] in ('api','worker') and any(pathlib.Path(a).name=='docmill' for a in args[:-1]):
  assert p.stat().st_uid != 0, 'application role is running as root'
  env=dict(item.split('=',1) for item in (p/'environ').read_bytes().decode().split('\\0') if '=' in item)
  found[args[-1]]=env['DOCMILL_STORAGE']
assert set(found)=={'api','worker'}, found
assert found['api']==found['worker']
print(json.dumps(found))'''
    return json.loads(run_python(machine, source))


with subtest('fresh alpha boot, runtime credential, and authenticated report'):
    alpha.start()
    alpha.wait_for_unit('multi-user.target')
    alpha.fail('ip -4 route show default | grep .')
    token_a = secrets.token_hex(24)
    provision_secret(alpha, token_a)
    ready(alpha)
    alpha.wait_for_unit('docmill-worker.service', timeout=30)
    assert request(alpha, '127.0.0.1', '/jobs', body={'label': 'unauthorized'})[0] == 401
    label_a = 'Alpha-' + secrets.token_hex(8)
    job_a = submit(alpha, '127.0.0.1', token_a, label_a)
    digest_a = finish(alpha, '127.0.0.1', token_a, job_a, label_a)
    paths = assert_service_users(alpha)
    alpha.fail('runuser -u nobody -- cat /run/secrets/docmill-api')
    alpha.fail('runuser -u nobody -- cat ' + shlex.quote(paths['api'] + '/' + job_a + '.svg'))

with subtest('queued work survives loss of Redis wake-up data and backend restarts'):
    alpha.succeed('systemctl stop docmill-worker.service')
    queued = [(submit(alpha, '127.0.0.1', token_a, label), label)
              for label in ['Queued-' + secrets.token_hex(8) for _ in range(3)]]
    alpha.succeed('redis-cli -h 127.0.0.1 -p 6379 FLUSHALL')
    alpha.succeed('systemctl restart postgresql.service redis-docmill.service')
    ready(alpha)
    alpha.succeed('systemctl start docmill-worker.service')
    for identity, label in queued:
        finish(alpha, '127.0.0.1', token_a, identity, label)
    assert finish(alpha, '127.0.0.1', token_a, job_a, label_a) == digest_a

with subtest('supervisor replaces a killed worker'):
    old_pid = alpha.succeed('systemctl show --value -p MainPID docmill-worker.service').strip()
    alpha.succeed('systemctl kill --signal=SIGKILL docmill-worker.service')
    alpha.wait_until_succeeds(
        'p=$(systemctl show --value -p MainPID docmill-worker.service); '
        'test "$p" -gt 0 && test "$p" != ' + shlex.quote(old_pid), timeout=30)
    label = 'Restart-' + secrets.token_hex(8)
    finish(alpha, '127.0.0.1', token_a,
           submit(alpha, '127.0.0.1', token_a, label), label)

with subtest('full guest reboot preserves original data and reports'):
    previous_boot = alpha.succeed('cat /proc/sys/kernel/random/boot_id').strip()
    alpha.shutdown()
    alpha.start()
    alpha.wait_for_unit('multi-user.target')
    assert alpha.succeed('cat /proc/sys/kernel/random/boot_id').strip() != previous_boot
    # /run credentials are supplied again by the external provisioning system.
    provision_secret(alpha, token_a)
    ready(alpha)
    assert finish(alpha, '127.0.0.1', token_a, job_a, label_a) == digest_a
    for identity, label in queued:
        finish(alpha, '127.0.0.1', token_a, identity, label)
    assert_service_users(alpha)

with subtest('same module creates a genuinely separate clean deployment'):
    beta.start()
    beta.wait_for_unit('multi-user.target')
    beta.fail('ip -4 route show default | grep .')
    token_b = secrets.token_hex(24)
    provision_secret(beta, token_b)
    ready(beta)
    assert request(beta, '127.0.0.1', '/jobs/' + job_a, token_b)[0] == 404
    assert request(beta, '127.0.0.1', '/jobs', token_a, {'label': 'wrong credential'})[0] == 401
    label_b = 'Beta-' + secrets.token_hex(8)
    job_b = submit(alpha, 'beta', token_b, label_b)
    finish(alpha, 'beta', token_b, job_b, label_b)
    assert request(alpha, '127.0.0.1', '/jobs/' + job_b, token_a)[0] == 404
    assert_service_users(beta)

with subtest('public API works cross-machine, backend services stay private'):
    assert request(beta, 'alpha', '/jobs/' + job_a, token_a)[0] == 200
    probe = '''import socket,sys
for port in (5432,6379):
 s=socket.socket();s.settimeout(2)
 assert s.connect_ex((sys.argv[1],port)) != 0, 'backend is externally reachable'
 s.close()'''
    run_python(beta, probe, 'alpha')
    run_python(alpha, probe, 'beta')

print('DOCMILL_DEPLOYMENT_VERIFIED')

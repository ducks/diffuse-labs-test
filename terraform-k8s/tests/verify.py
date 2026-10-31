import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import time
import xml.etree.ElementTree as ET

result = {'phases': [], 'reports_checked': 0}


def until(check, description, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except (AssertionError, ValueError, KeyError, IndexError):
            pass
        time.sleep(0.25)
    raise AssertionError('Timed out: ' + description)


def kube(namespace, command):
    return cluster.succeed('kubectl -n ' + shlex.quote(namespace) + ' ' + command)


def boot():
    cluster.wait_for_unit('k3s.service')
    cluster.wait_until_succeeds('kubectl get nodes --no-headers | grep -w Ready', timeout=240)
    cluster.wait_until_succeeds('kubectl -n kube-system rollout status deployment/coredns --timeout=90s', timeout=180)
    cluster.wait_until_succeeds('kubectl -n kube-system rollout status deployment/local-path-provisioner --timeout=90s', timeout=180)


def provision(namespace, port):
    api_token, password = secrets.token_hex(24), secrets.token_hex(24)
    cluster.succeed('kubectl create namespace ' + namespace)
    directory = '/root/' + namespace
    cluster.succeed('mkdir -p ' + directory + '; cp -r /etc/task-deployment/. ' + directory + '/')
    cluster.succeed('printf %s ' + shlex.quote(api_token) + ' > ' + directory + '/api-token')
    cluster.succeed('printf %s ' + shlex.quote(password) + ' > ' + directory + '/db-password')
    kube(namespace, 'create secret generic runtime-credentials --from-file=api-token=' + directory + '/api-token --from-file=db-password=' + directory + '/db-password')
    env = {'namespace': namespace, 'kubeconfig_path': '/etc/rancher/k3s/k3s.yaml', 'api_node_port': port}
    cluster.succeed('printf %s ' + shlex.quote(json.dumps(env)) + ' > ' + directory + '/terraform.tfvars.json')
    cluster.succeed('terraform -chdir=' + directory + ' init -input=false -no-color > ' + directory + '/init.log 2>&1')
    cluster.succeed('terraform -chdir=' + directory + ' apply -auto-approve -input=false -no-color > ' + directory + '/apply.log 2>&1')
    return {'namespace': namespace, 'port': port, 'token': api_token, 'directory': directory}


def request(env, path, body=None, authorized=True, token=None):
    code = '''import base64,json,sys,urllib.request,urllib.error
port,path,body,token=json.loads(sys.argv[1])
headers={} if token is None else {'Authorization':'Bearer '+token}
data=None if body is None else json.dumps(body).encode()
if data is not None:headers['Content-Type']='application/json'
try:r=urllib.request.urlopen(urllib.request.Request('http://192.168.1.1:'+str(port)+path,data=data,headers=headers),timeout=3)
except urllib.error.HTTPError as e:r=e
except urllib.error.URLError:
 print(json.dumps({'status':0,'body':''}));sys.exit(0)
print(json.dumps({'status':r.status,'body':base64.b64encode(r.read()).decode()}))'''
    value = [env['port'], path, body, (token or env['token']) if authorized else None]
    rc, output = cluster.execute('python -c ' + shlex.quote(code) + ' ' + shlex.quote(json.dumps(value)))
    if rc:
        return 0, b''
    parsed = json.loads(output)
    return parsed['status'], base64.b64decode(parsed['body'])


def ready(env):
    until(lambda: request(env, '/health')[0] == 200, 'API readiness', timeout=180)


def submit(env, label):
    status, body = request(env, '/jobs', {'label': label})
    assert status == 202, (status, body)
    return json.loads(body)['id']


def finish(env, identity, label):
    def done():
        status, body = request(env, '/jobs/' + identity)
        return status == 200 and json.loads(body)['state'] == 'done'
    until(done, 'report completed: ' + identity)
    status, data = request(env, '/reports/' + identity + '.svg')
    assert status == 200
    tree = ET.fromstring(data)
    assert label in ''.join(tree.itertext())
    result['reports_checked'] += 1
    return hashlib.sha256(data).hexdigest()


def pod(namespace, role):
    return json.loads(kube(namespace, 'get pods -l app=' + role + ' -o json'))['items'][0]


def replaced(namespace, role, old_uid):
    value = pod(namespace, role)
    return value['metadata']['uid'] != old_uid and any(
        item['type'] == 'Ready' and item['status'] == 'True'
        for item in value.get('status', {}).get('conditions', []))


def destroy(env):
    directory, namespace = env['directory'], env['namespace']
    cluster.succeed('terraform -chdir=' + directory + ' destroy -auto-approve -input=false -no-color > ' + directory + '/destroy.log 2>&1')
    def empty():
        objects = json.loads(kube(namespace, 'get deployments,statefulsets,daemonsets,services,jobs,pvc,pods,endpointslices -o json'))['items']
        volumes = json.loads(cluster.succeed('kubectl get pv -o json'))['items']
        return not objects and not any(v['spec'].get('claimRef', {}).get('namespace') == namespace for v in volumes)
    until(empty, 'managed resources and volumes removed', timeout=120)
    assert not cluster.succeed('terraform -chdir=' + directory + ' state list').strip()
    assert kube(namespace, 'get secret runtime-credentials -o name').strip()


try:
    cluster.start()
    with subtest('offline cluster and fresh Terraform deployment'):
        boot()
        a = provision('docmill-alpha', 30080)
        ready(a)
        assert request(a, '/jobs', {'label': 'unauthorized'}, authorized=False)[0] == 401
        label = 'Alpha-' + secrets.token_hex(8)
        identity = submit(a, label)
        original = finish(a, identity, label)
        assert int(kube(a['namespace'], 'exec deployment/api -- id -u').strip()) != 0
        assert int(kube(a['namespace'], 'exec deployment/worker -- id -u').strip()) != 0
        result['phases'].append('fresh-deployment')

    with subtest('worker is replaced at an acknowledged render barrier'):
        ns = a['namespace']
        kube(ns, 'exec deployment/api -- touch /reports/.render-pause')
        queued = [(submit(a, value), value) for value in ['Queued-' + secrets.token_hex(8) for _ in range(3)]]
        until(lambda: cluster.execute('kubectl -n ' + ns + ' exec deployment/api -- test -s /reports/.render-entered')[0] == 0, 'renderer barrier acknowledgement')
        old_name = kube(ns, 'exec deployment/api -- cat /reports/.render-entered').strip()
        old_uid = json.loads(kube(ns, 'get pod ' + old_name + ' -o json'))['metadata']['uid']
        kube(ns, 'exec deployment/redis -- redis-cli FLUSHALL')
        assert kube(ns, 'exec deployment/redis -- redis-cli DBSIZE').strip() == '0'
        kube(ns, 'delete pod ' + old_name + ' --grace-period=0 --force --wait=false')
        until(lambda: replaced(ns, 'worker', old_uid), 'replacement worker')
        kube(ns, 'exec deployment/api -- rm -f /reports/.render-pause /reports/.render-entered')
        for job, value in queued:
            finish(a, job, value)
        count = kube(ns, "exec deployment/api -- python -c 'from pathlib import Path; print(len(list(Path(\"/reports\").glob(\"*.svg\"))))'")
        assert int(count.strip()) == 4
        result['phases'].append('acknowledged-worker-loss')

    with subtest('database and cache pod replacement retains reports'):
        for role in ['postgres', 'redis']:
            old_uid = pod(ns, role)['metadata']['uid']
            kube(ns, 'delete pods -l app=' + role + ' --wait=false')
            until(lambda: replaced(ns, role, old_uid), 'replacement ' + role)
        ready(a)
        assert finish(a, identity, label) == original
        value = 'After-backends-' + secrets.token_hex(8)
        finish(a, submit(a, value), value)
        result['phases'].append('backend-replacement')

    with subtest('cold boot retains data and Terraform converges without drift'):
        boot_id = cluster.succeed('cat /proc/sys/kernel/random/boot_id').strip()
        cluster.shutdown()
        cluster.start()
        boot()
        assert cluster.succeed('cat /proc/sys/kernel/random/boot_id').strip() != boot_id
        ready(a)
        assert finish(a, identity, label) == original
        cluster.succeed('terraform -chdir=' + a['directory'] + ' plan -detailed-exitcode -input=false -no-color > ' + a['directory'] + '/plan.log 2>&1')
        result['phases'].append('cold-boot-and-no-drift')

    with subtest('same configuration deploys independent namespace and credentials'):
        b = provision('docmill-beta', 30081)
        ready(b)
        assert request(b, '/jobs/' + identity)[0] == 404
        assert request(b, '/jobs', {'label': 'wrong-key'}, token=a['token'])[0] == 401
        beta_label = 'Beta-' + secrets.token_hex(8)
        beta_job = submit(b, beta_label)
        beta_hash = finish(b, beta_job, beta_label)
        assert request(a, '/jobs/' + beta_job)[0] == 404
        result['phases'].append('namespace-isolation')

    with subtest('Terraform destroy cleans resources without harming another deployment'):
        destroy(a)
        ready(b)
        assert finish(b, beta_job, beta_label) == beta_hash
        destroy(b)
        result['phases'].append('destroy-and-volume-cleanup')

    result['passed'] = True
    (Path(os.environ['out']) / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('TERRAFORM_K8S_SPIKE_VERIFIED ' + json.dumps(result))
except Exception:
    print(cluster.succeed('kubectl get pods,pvc,services -A -o wide || true'))
    print(cluster.succeed('kubectl get events -A --sort-by=.metadata.creationTimestamp | tail -n 35 || true'))
    print(cluster.succeed("find /root/docmill-* -maxdepth 1 -name '*.log' -exec tail -n 40 {} + 2>/dev/null || true"))
    for namespace in ['docmill-alpha', 'docmill-beta']:
        print(cluster.succeed('kubectl -n ' + namespace + ' logs -l app=postgres --tail=60 --prefix=true 2>&1 || true'))
        print(cluster.succeed('kubectl -n ' + namespace + ' logs -l app=migrate --tail=40 --prefix=true 2>&1 || true'))
    raise

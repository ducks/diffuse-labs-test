"""Fresh native controls for the Terraform/K3s task; no model calls."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT/'terraform-k8s'
assert (TASK/'default.nix').read_bytes() == (TASK/'tests/default.nix').read_bytes(), 'Native and Harbor verifier expressions must match'
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
run = ROOT/'logs/terraform-k8s'/('controls-'+stamp)
run.mkdir(parents=True)
snapshot = run/'task'
shutil.copytree(TASK, snapshot, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
reference = json.loads((TASK/'solution/main.tf.json').read_text())
volatile = copy.deepcopy(reference)
volumes = volatile['resource']['kubernetes_deployment_v1']['postgres']['spec']['template']['spec']['volume']
for volume in volumes:
    if volume['name'] == 'database':
        volume.pop('persistent_volume_claim')
        volume['empty_dir'] = {}
controls = [
    ('canonical', TASK/'solution', True, None),
    ('alternate-init-containers', ROOT/'pilots/terraform-k8s-codex-001/deployment', True, None),
    ('no-op', TASK/'deployment', False, 'fresh-deployment'),
    ('volatile-postgres', volatile, False, 'backend-replacement'),
    ('reboot-permissions', ROOT/'pilots/terraform-k8s-claux-001/opus/deployment', False, 'cold-boot-and-no-drift'),
]
phases = ['fresh-deployment', 'acknowledged-worker-loss', 'backend-replacement',
          'cold-boot-and-no-drift', 'namespace-isolation', 'destroy-and-volume-cleanup']
results = []
print('Control directory: '+str(run), flush=True)
for name, source, expected, failed_phase in controls:
    candidate = run/name
    if isinstance(source, dict):
        candidate.mkdir()
        (candidate/'main.tf.json').write_text(json.dumps(source, indent=2)+'\n')
        shutil.copyfile(TASK/'deployment/.terraform.lock.hcl', candidate/'.terraform.lock.hcl')
    else:
        shutil.copytree(source, candidate)
    log = run/(name+'.log')
    with log.open('w') as output:
        proc = subprocess.run(['nix-build', str(snapshot), '--argstr', 'deploymentDir', str(candidate),
             '--argstr', 'runName', 'terraform-control-'+name+'-'+stamp.lower(),
             '--no-out-link', '--max-jobs', '1', '--cores', '2'],
             stdout=output, stderr=subprocess.STDOUT, timeout=1800)
    text = log.read_text()
    marker = 'TERRAFORM_K8S_SPIKE_VERIFIED ' if proc.returncode == 0 else 'TERRAFORM_K8S_SPIKE_FAILED '
    messages = [line.split(marker, 1)[1] for line in text.splitlines() if line.startswith(marker)]
    record = {'control': name, 'expected_pass': expected, 'exit_code': proc.returncode,
              'expected_failure_phase': failed_phase,
              'submission_files': {str(p.relative_to(candidate)): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted(candidate.rglob('*')) if p.is_file()},
              'log': str(log.relative_to(ROOT))}
    if not messages:
        record.update(expectation_met=False, infrastructure_error='No task result marker; inspect build/VM failure')
    else:
        result = json.loads(messages[-1]); passed = proc.returncode == 0 and result.get('passed') is True
        observed_phase = None if passed else phases[len(result['phases'])]
        record.update(passed=passed, failure_phase=observed_phase, result=result,
                      expectation_met=passed == expected and observed_phase == failed_phase)
    if proc.returncode == 0:
        record['result_store_path'] = next(line for line in reversed(text.splitlines()) if line.startswith('/nix/store/'))
    results.append(record)
    (run/'summary.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(record), flush=True)
    if not record['expectation_met']:
        raise SystemExit('Control did not match expectation: '+name)
print('All native control expectations met.', flush=True)

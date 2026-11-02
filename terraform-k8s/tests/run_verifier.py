"""Separate-container Harbor adapter for the native K3s lifecycle verifier."""
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

logs = Path('/logs/verifier')
# Infrastructure prerequisites fail without publishing a model reward.
with open('/dev/kvm', 'rb', buffering=0) as kvm:
    if fcntl.ioctl(kvm, 0xAE00, 0) != 12:
        raise RuntimeError('KVM API version is not supported')


def reject(reason):
    result = {'passed': False, 'phases': [], 'error': 'Invalid submission: '+reason}
    (logs/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    (logs/'reward.txt').write_text('0\n')
    print(json.dumps(result))
    raise SystemExit(0)


source = Path('/workspace/deployment')
if not source.is_dir() or source.is_symlink():
    reject('deployment must be a regular directory')
with tempfile.TemporaryDirectory(prefix='terraform-verifier-') as scratch:
    root = Path(scratch)
    task = root/'task'
    shutil.copytree('/opt/task-fixture', task)
    (task/'tests').mkdir()
    shutil.copyfile('/tests/default.nix', task/'default.nix')
    shutil.copyfile('/tests/verify.py', task/'tests/verify.py')
    candidate = root/'submission'
    candidate.mkdir()
    total = 0
    count = 0
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if path.is_symlink():
            reject('submission symlinks are not supported')
        if path.is_dir():
            continue
        if not path.is_file():
            reject('submission contains a special file')
        count += 1
        total += path.stat().st_size
        if count > 100 or total > 20*1024*1024:
            reject('submission exceeds file/byte limit')
        dest = candidate/relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    log = logs/'native-verifier.log'
    with log.open('w') as output:
        proc = subprocess.run(['nix-build', str(task), '--argstr', 'deploymentDir', str(candidate),
            '--argstr', 'runName', 'terraform-harbor-'+str(time.time_ns()),
            '--no-out-link', '--max-jobs', '1', '--cores', '2'],
            stdout=output, stderr=subprocess.STDOUT, timeout=1650)
    text = log.read_text()
    if proc.returncode == 0:
        store = next(line for line in reversed(text.splitlines()) if line.startswith('/nix/store/'))
        result = json.loads((Path(store)/'result.json').read_text())
        assert result.get('passed') and len(result['phases']) == 6
        reward = 1
    else:
        marker = 'TERRAFORM_K8S_SPIKE_FAILED '
        messages = [line[len(marker):] for line in text.splitlines() if line.startswith(marker)]
        if not messages:
            raise RuntimeError('Native build/VM infrastructure failed; inspect native-verifier.log')
        result = json.loads(messages[-1])
        reward = 0
    (logs/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    (logs/'reward.txt').write_text(str(reward)+'\n')
    print(json.dumps({'reward':reward, **result}))

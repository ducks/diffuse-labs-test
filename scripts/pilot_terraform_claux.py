"""Opt-in isolated Terraform/K3s pilot through Claux and OpenRouter."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model', required=True)
parser.add_argument('--binary', type=Path, required=True)
parser.add_argument('--seconds', type=int, default=900)
parser.add_argument('--model-rounds', type=int, default=200)
parser.add_argument('--reasoning-effort', default='low')
parser.add_argument('--key-file', type=Path,
                    default=Path.home()/'.config/claux/credentials/openrouter')
parser.add_argument('--preflight-only', action='store_true')
args = parser.parse_args()
if not 30 <= args.seconds <= 1800 or not 1 <= args.model_rounds <= 2000:
    parser.error('seconds must be 30–1800 and model rounds 1–2000')
binary = args.binary.resolve(strict=True)
key = args.key_file.read_text().strip()
if not key:
    parser.error('credential file is empty')
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
run = ROOT/'logs/pilots'/('terraform-claux-'+stamp)
run.mkdir(parents=True)
name = 'diffuse-terraform-claux-'+stamp.lower()
workspace = run/'workspace'
subprocess.run(['python3', str(ROOT/'scripts/export_terraform_task.py'), str(workspace)], check=True)
shutil.copytree(ROOT/'terraform-k8s', run/'task-snapshot',
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
prompt = (ROOT/'pilots/terraform-k8s-codex-001/prompt.txt').read_text().replace('900 seconds', str(args.seconds)+' seconds')
(run/'prompt.txt').write_text(prompt)
config = '\n'.join([
    'model = '+json.dumps(args.model),
    'openai_base_url = "https://openrouter.ai/api/v1"',
    'openai_provider_name = "openrouter"', 'openai_protocol = "openrouter"',
    'openai_api_key_env = "OPENROUTER_API_KEY"',
    'openai_reasoning_effort = '+json.dumps(args.reasoning_effort),
    'permission_mode = "bypass"', 'native_tool_filesystem_policy = "workspace_only"',
    'bash_filesystem_policy = "unrestricted"', 'max_rounds = '+str(args.model_rounds),
    'max_tokens = 8192', '',
])
(run/'config.toml').write_text(config)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
source_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
plan = {'model': args.model, 'harness': 'claux', 'provider': 'openrouter',
        'reasoning_effort': args.reasoning_effort, 'agent_timeout_seconds': args.seconds,
        'max_model_rounds': args.model_rounds, 'max_output_tokens_per_round': 8192,
        'model_attempts': 0 if args.preflight_only else 1, 'retries': 0,
        'source_commit': source_commit, 'binary_sha256': sha(binary),
        'runner_sha256': sha(Path(__file__)), 'container_cpus': 2, 'container_memory_gib': 8,
        'image': 'diffuse-terraform-pilot:001',
        'isolation': 'Docker with private Nix store, KVM and public workspace; no host home/store or daemon mounts',
        'context': 'Fresh single Claux session; same public prompt and task as Codex pilot',
        'grading': 'Frozen private verifier after collection; no feedback or second attempt',
        'source_manifest': {str(p.relative_to(workspace)): sha(p)
                            for p in sorted(workspace.rglob('*')) if p.is_file()}}
(run/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
shutil.copyfile(__file__, run/'runner.py')
print('Pilot directory: '+str(run), flush=True)
summary = {'model': args.model, 'status': 'setup', 'model_started': False}
created = False


def call(*command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def collect(directory, destination, *, deployment=False):
    destination.mkdir()
    process = subprocess.Popen(['docker', 'cp', name+':'+directory, '-'], stdout=subprocess.PIPE)
    total = 0
    files = {}
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
            for item in archive:
                relative = Path(item.name).relative_to(Path(directory).name)
                if relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('unsafe artifact path')
                if not relative.parts or item.isdir():
                    continue
                if deployment and ('.terraform' in relative.parts or
                    relative.name.endswith(('.tfstate', '.tfstate.backup', '.tfplan')) or
                    relative.name == '.terraform.tfstate.lock.info'):
                    continue
                if not item.isfile():
                    raise ValueError('only regular artifact files are accepted')
                total += item.size
                if total > (20 if deployment else 100)*1024*1024 or len(files) >= 100:
                    raise ValueError('artifact collection limit exceeded')
                target = destination/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(item).read())
                files[str(relative)] = sha(target)
        if process.wait(timeout=30):
            raise RuntimeError('docker artifact collection failed')
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
    return files


try:
    call('docker', 'create', '--name', name, '--device=/dev/kvm', '--cpus=2',
         '--memory=8g', '--pids-limit=1024', '--security-opt=no-new-privileges',
         '-e', 'HOME=/agent-home', '-e', 'XDG_CONFIG_HOME=/agent-home/config',
         '-e', 'XDG_DATA_HOME=/agent-home/data',
         'diffuse-terraform-pilot:001', '/bin/sleep', 'infinity', stdout=subprocess.DEVNULL)
    created = True
    call('docker', 'start', name, stdout=subprocess.DEVNULL)
    call('docker', 'cp', str(workspace)+'/.', name+':/workspace')
    call('docker', 'exec', name, 'mkdir', '-p', '/agent-home', '/agent-bin', '/agent-lib', '/artifacts')
    call('docker', 'cp', str(run/'config.toml'), name+':/agent-home/config.toml')
    call('docker', 'cp', str(binary), name+':/agent-bin/claux')
    # Copy only Claux's runtime libraries, not the host filesystem or Nix store.
    linked = subprocess.check_output(['ldd', str(binary)], text=True)
    libraries = sorted(set(re.findall(r'=> (/\S+)', linked)))
    loader = next(Path(path) for path in libraries if 'ld-linux' in path)
    for library in libraries:
        call('docker', 'cp', str(Path(library).resolve()), name+':/agent-lib/'+Path(library).name)
    wrapper = run/'claux-run'
    wrapper.write_text('#!/bin/sh\nexec /agent-lib/'+loader.name+' --library-path /agent-lib /agent-bin/claux "$@"\n')
    wrapper.chmod(0o755)
    call('docker', 'cp', str(wrapper), name+':/agent-bin/claux-run')
    preflight = subprocess.run(['docker', 'exec', name, '/bin/bash', '-lc',
        'set -e; /agent-bin/claux-run --help; test -c /dev/kvm; '
        'test ! -S /var/run/docker.sock; test ! -e /workspace/tests; '
        'test ! -e /workspace/solution; test ! -e /home/urho; '
        'nix-instantiate --eval --strict -E "(import /opt/nixpkgs {}).lib.version"; '
        'terraform version; curl -fsS --max-time 20 -o /dev/null https://openrouter.ai/api/v1/models'],
        capture_output=True, text=True, timeout=60)
    (run/'preflight.txt').write_text(preflight.stdout+preflight.stderr)
    preflight.check_returncode()
    summary['preflight_passed'] = True
    if args.preflight_only:
        summary['status'] = 'preflight_only'
    else:
        command = ['docker', 'exec', '-e', 'OPENROUTER_API_KEY', name,
                   '/agent-bin/claux-run', '--config', '/agent-home/config.toml',
                   '-p', prompt, '--output-format', 'json', '--transcript', '/artifacts/transcript.json']
        (run/'command.json').write_text(json.dumps(command, indent=2)+'\n')
        environment = dict(os.environ, OPENROUTER_API_KEY=key)
        started = time.monotonic()
        summary['model_started'] = True
        with (run/'agent.stdout').open('w') as stdout, (run/'agent.stderr').open('w') as stderr:
            try:
                result = subprocess.run(command, env=environment, stdout=stdout, stderr=stderr,
                                        timeout=args.seconds)
                summary.update(agent_exit_code=result.returncode, timed_out=False)
            except subprocess.TimeoutExpired:
                summary.update(agent_exit_code=None, timed_out=True)
        summary['agent_wall_seconds'] = round(time.monotonic()-started, 2)
        call('docker', 'stop', '-t', '2', name, stdout=subprocess.DEVNULL)
        summary['submission_files'] = collect('/workspace/deployment', run/'submission', deployment=True)
        summary['artifact_files'] = collect('/artifacts', run/'artifacts')
        # Remove the disposable credential-bearing process before private grading.
        call('docker', 'rm', '-f', name, stdout=subprocess.DEVNULL)
        created = False
        transcript = run/'artifacts/transcript.json'
        if transcript.exists():
            data = json.loads(transcript.read_text())
            summary['usage'] = data.get('usage')
            summary['harness_outcome'] = data.get('outcome')
            summary['checkpoint_incomplete'] = data.get('outcome', {}).get('status') == 'running'
        summary['status'] = 'submission_collected'
        (run/'agent-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
        print(json.dumps(summary), flush=True)
        with (run/'verifier.log').open('w') as log:
            grade = subprocess.run(['nix-build', str(run/'task-snapshot'), '--argstr',
                    'deploymentDir', str(run/'submission'), '--no-out-link', '--max-jobs', '1', '--cores', '2'],
                    stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        failure = summary.get('harness_outcome', {}).get('failure', {}).get('kind')
        unavailable = failure in {'rate_limited', 'unavailable', 'authentication', 'model_not_found', 'network', 'protocol_error'}
        summary.update(status='evaluated', verifier_exit_code=grade.returncode, passed=grade.returncode == 0,
                       model_outcome='unavailable' if unavailable else ('evaluated_pass' if grade.returncode == 0 else 'evaluated_fail'))
        summary['cost_checkpoint_incomplete'] = summary.get('timed_out', False) or summary.get('checkpoint_incomplete', False)
        if grade.returncode == 0:
            store = next(line for line in reversed((run/'verifier.log').read_text().splitlines()) if line.startswith('/nix/store/'))
            summary['result_store_path'] = store
            summary['verifier_result'] = json.loads((Path(store)/'result.json').read_text())
except Exception as error:
    summary.update(status='runner_or_provider_error', error=str(error).replace(key, '[REDACTED]'))
    raise
finally:
    if created:
        subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL)
    # Raw artifacts remain private/gitignored; redact any accidental key echo.
    for path in [run/'agent.stdout', run/'agent.stderr', *list((run/'artifacts').glob('*.json'))]:
        if path.exists():
            path.write_text(path.read_text().replace(key, '[REDACTED]'))
    (run/'summary.json').write_text(json.dumps(summary, indent=2).replace(key, '[REDACTED]')+'\n')
    print(json.dumps(summary).replace(key, '[REDACTED]'), flush=True)

"""Opt-in, model-backed visual pilot; private grading only after all rounds."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT/'hyprland-visual'
FILES = ['hypr/hyprland.lua', 'waybar/config.jsonc', 'waybar/style.css',
         'foot/foot.ini', 'wofi/config', 'wofi/style.css']
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model', required=True, help='OpenRouter model supporting images and tools.')
parser.add_argument('--binary', type=Path, required=True)
parser.add_argument('--rounds', type=int, default=2, choices=range(1, 4))
parser.add_argument('--model-rounds', type=int, default=200, choices=range(1, 2001),
                    help='Per-invocation model round limit; defaults to Claux\'s normal 200.')
parser.add_argument('--seconds-per-round', type=int, default=180, choices=range(30, 601))
parser.add_argument('--key-file', type=Path, default=Path.home()/'.config/claux/credentials/openrouter')
args = parser.parse_args()
binary = args.binary.resolve(strict=True)
key = args.key_file.read_text().strip()
if not key:
    parser.error('empty credential file')
run = ROOT/'logs/pilots'/('hyprland-claux-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
run.mkdir(parents=True)
workspace = run/'workspace'
subprocess.run(['python', str(ROOT/'scripts/export_hyprland_task.py'), str(workspace)], check=True)
snapshot = run/'task-snapshot'
shutil.copytree(TASK, snapshot, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
home = run/'agent-home'
home.mkdir(mode=0o700)
(home/'config.toml').write_text('''
model = '''+json.dumps(args.model)+'''
openai_base_url = "https://openrouter.ai/api/v1"
openai_provider_name = "openrouter"
openai_protocol = "openrouter"
openai_api_key_env = "OPENROUTER_API_KEY"
permission_mode = "bypass"
native_fs_policy = "workspace_only"
bash_fs_policy = "unrestricted"
max_rounds = ''' + str(args.model_rounds) + '\n')
artifacts = run/'agent-artifacts'
artifacts.mkdir()
bound = ['bwrap', '--unshare-all', '--share-net', '--die-with-parent',
         '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib',
         '--ro-bind', '/lib64', '/lib64', '--ro-bind', '/bin', '/bin',
         '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
         '--bind', str(workspace), '/workspace',
         '--bind', str(home), '/agent-home', '--bind', str(artifacts), '/artifacts',
         '--ro-bind', str(binary), '/claux', '--chdir', '/workspace']
for path in ['/etc/ssl', '/etc/ca-certificates', '/etc/pki', '/etc/resolv.conf', '/etc/hosts', '/etc/nsswitch.conf', '/etc/passwd', '/etc/group']:
    if Path(path).exists():
        bound += ['--ro-bind', path, path]
# Do not put the real key in process arguments, config, or logged commands.
env = {'PATH':'/usr/bin:/bin', 'HOME':'/agent-home', 'USER':os.environ.get('USER', 'agent'),
       'OPENROUTER_API_KEY':key, 'LANG':'C.UTF-8', 'TERM':'dumb'}
plan = {'model':args.model, 'rounds':args.rounds, 'seconds_per_round':args.seconds_per_round,
        'max_model_rounds_per_invocation':args.model_rounds, 'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
        'isolation':'Bubblewrap filesystem/PID namespaces; host home and Nix store absent; network for OpenRouter',
        'context':'Fresh Claux one-shot per visual round; configs, prior answer, and public screenshots retained',
        'grading':'Once, after all rounds; no private feedback to model', 'source_manifest':{
            str(p.relative_to(snapshot)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(snapshot.rglob('*')) if p.is_file()}}
(run/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
print('Pilot directory: '+str(run), flush=True)
rounds = []


def nix_preview(index):
    # Copy only regular submitted files into a fresh trusted capture directory.
    candidate = run/f'config-{index}'
    candidate.mkdir()
    for name in FILES:
        source = workspace/'config'/name
        for part in [workspace/'config', source.parent, source]:
            if part.is_symlink():
                raise ValueError('Symlink submission is not allowed: '+name)
        if not source.is_file() or source.stat().st_size > 1024*1024:
            raise ValueError('Invalid config file: '+name)
        dest = candidate/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    log = run/f'preview-{index}.log'
    with log.open('w') as stdout:
        result = subprocess.run(['nix-build', str(snapshot/'preview.nix'), '--argstr', 'configDir', str(candidate),
                                 '--no-out-link', '--max-jobs', '1', '--cores', '2'],
                                stdout=stdout, stderr=subprocess.STDOUT, timeout=600)
    if result.returncode:
        return candidate, None, log.read_text()[-4000:]
    store = next(line for line in reversed(log.read_text().splitlines()) if line.startswith('/nix/store/'))
    dest = workspace/'current'
    if dest.exists():
        dest.chmod(0o755)
        shutil.rmtree(dest)
    shutil.copytree(Path(store)/'captures', dest)
    dest.chmod(0o755)
    for p in dest.rglob('*'):
        p.chmod(0o755 if p.is_dir() else 0o644)
    return candidate, store, ''


try:
    # Preflight makes no model call and verifies the outer containment boundary.
    preflight = subprocess.run(bound+['--', '/bin/sh', '-c',
        'test ! -e /home/urho && test ! -e /nix/store && test ! -e /workspace/tests && '
        'test ! -e /workspace/solution && /claux --help && '
        'curl -fsS --max-time 20 -o /dev/null https://openrouter.ai/api/v1/models'],
        env=env, capture_output=True, text=True)
    (run/'preflight.txt').write_text(preflight.stdout + preflight.stderr)
    preflight.check_returncode()
    candidate, preview, feedback = nix_preview(0)
    if not preview:
        raise RuntimeError('Starting public preview failed: '+feedback)
    previous_answer = ''
    for index in range(1, args.rounds+1):
        prompt = f'''Implement instruction.md by editing only the six files under config/.
You are visual iteration {index} of {args.rounds}. The first three attached images
are the targets in order: empty, tiled, launcher. The next three are the current
desktop in the same order. Inspect the existing config and adjust it to match.
The host handles VM rendering between iterations; Nix/KVM are not available in
this editing sandbox. Do not change fixtures, helpers, targets, or VM code.
You have {args.seconds_per_round} seconds and at most {args.model_rounds} model rounds. Save your
edits and briefly describe them. There is no private grader feedback.
Previous iteration's answer: {previous_answer[-2500:]}
Public preview status: {feedback or 'all three scenes captured successfully'}
'''
        command = bound+['--', '/claux', '--config', '/agent-home/config.toml', '-p', prompt,
                         '--output-format', 'json', '--transcript', f'/artifacts/round-{index}.json']
        for folder in ['targets', 'current']:
            for name in ['empty', 'tiled', 'launcher']:
                if (workspace/folder/(name+'.png')).is_file():
                    command += ['--image', '/workspace/'+folder+'/'+name+'.png']
        started = time.monotonic()
        try:
            result = subprocess.run(command, env=env, capture_output=True, text=True,
                                    timeout=args.seconds_per_round)
        except subprocess.TimeoutExpired:
            record = {'round':index, 'timed_out':True, 'wall_seconds':round(time.monotonic()-started, 2)}
            rounds.append(record)
            previous_answer = 'Iteration reached its wall-clock limit; the saved config is retained.'
            print(json.dumps(record), flush=True)
            candidate, preview, feedback = nix_preview(index)
            record['public_preview_store'] = preview
            continue
        stdout = result.stdout.replace(key, '[REDACTED]')
        stderr = result.stderr.replace(key, '[REDACTED]')
        (run/f'round-{index}.stdout').write_text(stdout)
        (run/f'round-{index}.stderr').write_text(stderr)
        record = {'round':index, 'exit_code':result.returncode,
                  'wall_seconds':round(time.monotonic()-started, 2)}
        rounds.append(record)
        print(json.dumps(record), flush=True)
        response = json.loads(stdout)
        previous_answer = response.get('result', '')
        record['usage'] = response.get('usage')
        record['cost'] = response.get('cost')
        if result.returncode:
            message = response.get('outcome', {}).get('message', '')
            if 'configured limit' in message and 'model rounds' in message:
                record['round_budget_exhausted'] = True
                previous_answer = message
            else:
                raise RuntimeError('Claux failed; inspect saved stderr/JSON without retrying the model')
        candidate, preview, feedback = nix_preview(index)
        record['public_preview_store'] = preview
    with (run/'verifier.log').open('w') as stdout:
        grade = subprocess.run(['nix-build', str(snapshot), '--argstr', 'configDir', str(candidate),
                                '--no-out-link', '--max-jobs', '1', '--cores', '2'],
                               stdout=stdout, stderr=subprocess.STDOUT, timeout=900)
    summary = {'status':'evaluated', 'passed':grade.returncode == 0, 'rounds':rounds,
               'verifier_exit_code':grade.returncode}
except Exception as error:
    summary = {'status':'runner_or_provider_error', 'error':str(error).replace(key, '[REDACTED]'), 'rounds':rounds}
    raise
finally:
    for path in artifacts.rglob('*.json'):
        path.write_text(path.read_text().replace(key, '[REDACTED]'))
    # Credential was inherited only in the child environment; never stored here.
    (run/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary), flush=True)

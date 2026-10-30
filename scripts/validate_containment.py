"""Behavioral controls for the incident-inspired dataset repair task."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'dataset-containment'
parser = argparse.ArgumentParser()
parser.add_argument('--container', action='store_true')
args = parser.parse_args()
if args.container:
    subprocess.run(['docker', 'build', '-t', 'diffuse-dataset-containment:local',
                    str(TASK / 'environment')], check=True)
service = (TASK / 'solution/service.py').read_text()
repair = (TASK / 'solution/repair.py').read_text()
broken_service = (TASK / 'environment/app/service.py').read_text()
broken_repair = (TASK / 'environment/app/repair.py').read_text()
# Alternative enforces the boundary in the loader rather than trusting the
# deployment's ALLOWED_ROOT value. Both satisfy the observable policy.
loader_enforced = service.replace("def load_input(manifest, inputs, allowed):\n",
                                  "def load_input(manifest, inputs, allowed):\n    allowed = inputs\n")
without_config_boundary = repair.replace("    settings['ALLOWED_ROOT'] = str(root / 'var/lib/dataset-worker/incoming')\n", '')
access_only = repair.replace("WHERE principal='worker'\")", "WHERE principal='worker' AND kind='access'\")")
no_boundary = (service, without_config_boundary)
no_schedule = repair.replace("        db.execute(\"UPDATE schedules SET active=0 WHERE owner='worker' AND kind='dataset-export'\")", '        pass')
all_schedules = repair.replace("WHERE owner='worker' AND kind='dataset-export'", '')
all_credentials = repair.replace(" WHERE principal='worker'", '')
delete_evidence = repair.replace('    restart_worker(root)',
    "    with sqlite3.connect(root / 'var/lib/dataset-api/state.sqlite3') as db:\n        db.execute('DELETE FROM audit')\n    restart_worker(root)")
# Requeue known partial jobs, then use the original worker to blindly republish.
blind_repair = repair.replace('    restart_worker(root)',
    '''    with sqlite3.connect(root / 'var/lib/dataset-api/state.sqlite3') as db:
        db.execute("UPDATE jobs SET state='queued' WHERE state='retry'")
    restart_worker(root)''')
controls = [
    ('canonical', service, repair, True),
    ('alternative-loader-policy', loader_enforced, without_config_boundary, True),
    ('restart-only', broken_service, broken_repair, False),
    ('access-only-rotation', service, access_only, False),
    ('boundary-left-open', *no_boundary, False),
    ('unauthorized-schedule-left', service, no_schedule, False),
    ('disable-all-scheduling', service, all_schedules, False),
    ('revoke-unrelated-client', service, all_credentials, False),
    ('ignore-interrupted-jobs', broken_service, repair, False),
    ('blind-republish', broken_service, blind_repair, False),
    ('delete-audit-evidence', service, delete_evidence, False),
]
logs = ROOT / 'logs/dataset-containment'
logs.mkdir(parents=True, exist_ok=True)
results = []
with tempfile.TemporaryDirectory() as scratch:
    for name, worker_code, repair_code, expected in controls:
        compile(worker_code, name + '/service.py', 'exec')
        compile(repair_code, name + '/repair.py', 'exec')
        candidate = Path(scratch) / name
        candidate.mkdir()
        (candidate / 'service.py').write_text(worker_code)
        (candidate / 'repair.py').write_text(repair_code)
        env = dict(os.environ, CANDIDATE_DIR=str(candidate), SERVICE_DIR=str(TASK / 'environment/service'))
        command = [sys.executable, str(TASK / 'tests/verify.py')]
        if args.container:
            command = ['docker', 'run', '--rm', '--network', 'none',
                       '-v', f"{TASK / 'tests'}:/tests:ro", '-v', f'{candidate}:/candidate:ro',
                       'diffuse-dataset-containment:local', 'sh', '-c',
                       'cp /candidate/*.py /app/; sh /tests/test.sh; '
                       'status=$?; echo REWARD=$(cat /logs/verifier/reward.txt); exit $status']
        proc = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)
        passed = proc.returncode == 0
        reward_ok = not args.container or f'REWARD={int(expected)}' in proc.stdout.splitlines()
        matched = passed == expected and reward_ok
        suffix = '-container' if args.container else ''
        (logs / (name + suffix + '.txt')).write_text(proc.stdout + proc.stderr)
        results.append(dict(control=name, expected_pass=expected, passed=passed, expectation_met=matched))
        print(f'{name}: {"PASS" if passed else "FAIL"}; expected {"PASS" if expected else "FAIL"}', flush=True)
        if not matched:
            print((proc.stdout + proc.stderr)[-4000:])
filename = 'validation-container.json' if args.container else 'validation.json'
(logs / filename).write_text(json.dumps(results, indent=2) + '\n')
raise SystemExit(0 if all(r['expectation_met'] for r in results) else 1)

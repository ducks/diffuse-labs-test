"""Run positive and negative controls without changing the agent's starting files."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "session-recovery"
parser = argparse.ArgumentParser()
parser.add_argument("--container", action="store_true",
                    help="Run real /tests/test.sh entry point in Docker")
args = parser.parse_args()
if args.container:
    subprocess.run(["docker", "build", "-t", "diffuse-session-recovery:local",
                    str(TASK / "environment")], check=True)
baseline = (TASK / "environment/app/runner.py").read_text()
reference = (TASK / "solution/runner.py").read_text()
alternate = reference.replace(
    '        result = tool_service.lookup(store, call["id"])\n'
    '        if result is None:\n'
    '            result = tool_service.execute(store, call["id"], call["name"], call["arguments"])',
    '        result = tool_service.execute(store, call["id"], call["name"], call["arguments"])')
assert alternate != reference
skip = baseline.replace('        state["messages"].pop()',
                        '        state["messages"].pop()\n        state["next"] += 1')
reset = baseline.replace('    while state["next"] < len(plan):',
                        '    state["next"] = 0\n    state["messages"] = state["messages"][:1]\n'
                        '    while state["next"] < len(plan):')
controls = [
    ("canonical", reference, True),
    ("alternative-idempotent-replay", alternate, True),
    ("no-op-original-bug", baseline, False),
    ("shortcut-skip-pending", skip, False),
    ("shortcut-restart-plan", reset, False),
]
results = []
failed = False
with tempfile.TemporaryDirectory() as scratch:
    for name, code, should_pass in controls:
        runner = Path(scratch) / f"{name}.py"
        runner.write_text(code)
        env = dict(os.environ, RUNNER=str(runner),
                   SERVICE_DIR=str(TASK / "environment/service"))
        command = [sys.executable, str(TASK / "tests/verify.py")]
        if args.container:
            command = ["docker", "run", "--rm", "--network", "none",
                       "-v", f"{TASK / 'tests'}:/tests:ro",
                       "-v", f"{runner}:/candidate.py:ro",
                       "diffuse-session-recovery:local", "sh", "-c",
                       "cp /candidate.py /app/runner.py; sh /tests/test.sh; "
                       "status=$?; echo REWARD=$(cat /logs/verifier/reward.txt); exit $status"]
        proc = subprocess.run(command,
                              env=env, capture_output=True, text=True, timeout=120)
        passed = proc.returncode == 0
        reward_ok = not args.container or (
            f"REWARD={int(should_pass)}" in proc.stdout.splitlines())
        matched = passed == should_pass and reward_ok
        failed |= not matched
        results.append({"control": name, "expected_pass": should_pass,
                        "passed": passed, "expectation_met": matched})
        print(f'{name}: {"PASS" if passed else "FAIL"} (expected '
              f'{"PASS" if should_pass else "FAIL"})', flush=True)
        logs = ROOT / "logs"
        logs.mkdir(exist_ok=True)
        suffix = "-container" if args.container else ""
        (logs / f"{name}{suffix}.txt").write_text(proc.stdout + proc.stderr)
        if not matched:
            print(proc.stdout + proc.stderr)
filename = "validation-container.json" if args.container else "validation.json"
(ROOT / "logs" / filename).write_text(json.dumps(results, indent=2) + "\n")
raise SystemExit(1 if failed else 0)

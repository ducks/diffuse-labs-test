"""Positive and negative controls for the streaming task, locally or in Docker."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "streaming-gateway"
parser = argparse.ArgumentParser()
parser.add_argument("--container", action="store_true")
args = parser.parse_args()
if args.container:
    subprocess.run(["docker", "build", "-t", "diffuse-streaming-gateway:local",
                    str(TASK / "environment")], check=True)
reference = (TASK / "solution/gateway.py").read_text()
baseline = (TASK / "environment/app/gateway.py").read_text()
alternate = reference[:reference.index("    async def stream")] + '''    async def stream(self, payload):
        last_error = None
        for name, limit in self.limits.items():
            if self.active[name] >= limit:
                continue
            self.active[name] += 1
            response = None
            try:
                try:
                    response = await self.transport.open(name, payload)
                    iterator = aiter(response)
                    while True:
                        first = await anext(iterator)
                        if first:
                            break
                except StopAsyncIteration:
                    return
                except UpstreamError as error:
                    last_error = error
                    continue
                yield first
                async for chunk in iterator:
                    if chunk:
                        yield chunk
                return
            finally:
                try:
                    if response is not None:
                        await response.aclose()
                finally:
                    self.active[name] -= 1
        raise GatewayUnavailable("no backend completed the request") from last_error
'''
retry_partial = reference.replace('                if committed:\n                    raise\n', '')
no_failover = reference.replace('                last_error = error', '                raise')
leak = reference.replace('                    self.active[name] -= 1', '                    pass')
buffered = reference.replace('                async for chunk in response:',
                             '                buffered = [chunk async for chunk in response]\n'
                             '                for chunk in buffered:')
controls = [("canonical", reference, True), ("alternative-prime-stream", alternate, True),
            ("no-op", baseline, False), ("retry-partial", retry_partial, False),
            ("disable-failover", no_failover, False), ("leak-capacity", leak, False),
            ("buffer-response", buffered, False),
            ("exit-zero-during-import", "import os\nos._exit(0)\n", False)]
results = []
logs = ROOT / "logs/streaming-gateway"
logs.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as scratch:
    for name, code, expected in controls:
        candidate = Path(scratch) / f"{name}.py"
        candidate.write_text(code)
        env = dict(os.environ, GATEWAY_PATH=str(candidate),
                   SERVICE_DIR=str(TASK / "environment/service"))
        command = [sys.executable, str(TASK / "tests/run_verifier.py")]
        if args.container:
            command = ["docker", "run", "--rm", "--network", "none",
                       "-v", f"{TASK / 'tests'}:/tests:ro",
                       "-v", f"{candidate}:/candidate.py:ro",
                       "diffuse-streaming-gateway:local", "sh", "-c",
                       "cp /candidate.py /app/gateway.py; sh /tests/test.sh; "
                       "status=$?; echo REWARD=$(cat /logs/verifier/reward.txt); exit $status"]
        proc = subprocess.run(command, env=env, capture_output=True, text=True, timeout=120)
        passed = proc.returncode == 0
        reward_ok = not args.container or f"REWARD={int(expected)}" in proc.stdout.splitlines()
        matched = passed == expected and reward_ok
        suffix = "-container" if args.container else ""
        (logs / f"{name}{suffix}.txt").write_text(proc.stdout + proc.stderr)
        results.append(dict(control=name, expected_pass=expected, passed=passed,
                            expectation_met=matched))
        print(f'{name}: {"PASS" if passed else "FAIL"}; expected '
              f'{"PASS" if expected else "FAIL"}', flush=True)
        if not matched:
            print(proc.stdout + proc.stderr)
filename = "validation-container.json" if args.container else "validation.json"
(logs / filename).write_text(json.dumps(results, indent=2) + "\n")
raise SystemExit(0 if all(r["expectation_met"] for r in results) else 1)

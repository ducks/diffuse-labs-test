"""Fail closed if a candidate import exits before the behavioral suite runs.

This trusted parent never imports candidate code. It requires a complete suite
result from its test subprocess rather than trusting exit status alone. It is
not a sandbox against arbitrary hostile Python that forges the child protocol.
"""
import ast
import json
from pathlib import Path
import subprocess
import sys

verifier = Path(__file__).with_name("verify.py")
expected = sum(
    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    and node.name.startswith("test_")
    for node in ast.walk(ast.parse(verifier.read_text()))
)
if expected == 0:
    raise RuntimeError("Verifier contains no behavioral tests")
try:
    result = subprocess.run([sys.executable, str(verifier)],
                            capture_output=True, text=True, timeout=110)
except subprocess.TimeoutExpired:
    raise SystemExit("Gateway verifier timed out before completing its suite")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
prefix = "GATEWAY_VERIFIER_RESULT "
reports = [line[len(prefix):] for line in result.stdout.splitlines()
           if line.startswith(prefix)]
if result.returncode != 0 or len(reports) != 1:
    raise SystemExit("Gateway verifier did not provide one successful complete-suite result")
try:
    summary = json.loads(reports[0])
except (ValueError, TypeError):
    raise SystemExit("Gateway verifier returned an invalid suite result")
if summary != {"tests_run": expected, "failures": 0, "errors": 0, "skipped": 0}:
    raise SystemExit("Gateway verifier did not execute every required test successfully")

"""Independent positive/negative controls for persistent tool acquisition."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'persistent-tools'
parser = argparse.ArgumentParser()
parser.add_argument('--container', action='store_true')
args = parser.parse_args()
if args.container:
    subprocess.run(['docker', 'build', '-t', 'diffuse-persistent-tools:local',
                    str(TASK / 'environment')], check=True)
reference = (TASK / 'solution/store.py').read_text()
baseline = (TASK / 'environment/app/store.py').read_text()
publication = '        atomic_write(self.manifest, json.dumps(active, sort_keys=True).encode())'
# Alternate validates a private temporary file, installing a durable content
# artifact only after validation rather than staging in the blob directory.
alternate = reference.replace('import re\n', 'import re\nimport tempfile\n')
a = alternate.index('        path = self.blobs / (digest +')
b = alternate.index("        fault('before-publish')", a)
alternate = alternate[:a] + '''        with tempfile.TemporaryDirectory(dir=self.root) as scratch:
            candidate = Path(scratch) / 'candidate.py'
            atomic_write(candidate, data)
            fault('staged')
            for case in cases:
                if self.executor(candidate, case['input']) != case['expected']:
                    raise ToolError('validation mismatch')
            fault('validated')
            atomic_write(self.blobs / (digest + '.py'), data)
        active = dict(active, **{name: digest})
''' + alternate[b:]
no_save = reference.replace(publication, '        pass  # never publish')
no_validation = reference.replace("            if self.executor(path, case['input']) != case['expected']:",
                                  '            if False:')
early_save = reference.replace("        fault('staged')", "        active[name] = digest\n" + publication + "\n        fault('staged')")
in_memory = reference.replace('    def _manifest(self):\n',
                              "    def _manifest(self):\n        return dict(getattr(self, '_cached', {}))\n")
in_memory = in_memory.replace(publication, '        self._cached = dict(active)')
overwrite = reference.replace('        digest = hashlib.sha256(data).hexdigest()',
                              '        digest = active.get(name, hashlib.sha256(data).hexdigest())')
hardcoded = reference.replace('        valid_name(name)\n        if not isinstance(source',
                              "        valid_name(name)\n        if name != 'word_count':\n            raise ToolError('unsupported tool')\n        if not isinstance(source")
controls = [('canonical', reference, True), ('alternative-private-stage', alternate, True),
            ('no-op', baseline, False), ('validate-never-save', no_save, False),
            ('skip-validation', no_validation, False), ('publish-before-validation', early_save, False),
            ('in-memory-only', in_memory, False), ('overwrite-active-source', overwrite, False),
            ('hardcoded-name', hardcoded, False)]
logs = ROOT / 'logs/persistent-tools'
logs.mkdir(parents=True, exist_ok=True)
results = []
with tempfile.TemporaryDirectory() as scratch:
    for name, code, expected in controls:
        candidate = Path(scratch) / (name + '.py')
        candidate.write_text(code)
        env = dict(os.environ, STORE_PATH=str(candidate), SERVICE_DIR=str(TASK / 'environment/service'))
        command = [sys.executable, str(TASK / 'tests/verify.py')]
        if args.container:
            command = ['docker', 'run', '--rm', '--network', 'none',
                       '-v', f"{TASK / 'tests'}:/tests:ro", '-v', f'{candidate}:/candidate.py:ro',
                       'diffuse-persistent-tools:local', 'sh', '-c',
                       'cp /candidate.py /app/store.py; sh /tests/test.sh; '
                       'status=$?; echo REWARD=$(cat /logs/verifier/reward.txt); exit $status']
        proc = subprocess.run(command, env=env, capture_output=True, text=True, timeout=120)
        passed = proc.returncode == 0
        reward_ok = not args.container or f'REWARD={int(expected)}' in proc.stdout.splitlines()
        matched = passed == expected and reward_ok
        suffix = '-container' if args.container else ''
        (logs / (name + suffix + '.txt')).write_text(proc.stdout + proc.stderr)
        results.append(dict(control=name, expected_pass=expected, passed=passed, expectation_met=matched))
        print(f'{name}: {"PASS" if passed else "FAIL"}; expected {"PASS" if expected else "FAIL"}', flush=True)
        if not matched:
            print(proc.stdout + proc.stderr)
filename = 'validation-container.json' if args.container else 'validation.json'
(logs / filename).write_text(json.dumps(results, indent=2) + '\n')
raise SystemExit(0 if all(r['expectation_met'] for r in results) else 1)

"""Run native NixOS deployment controls. Linux/KVM required; no model calls."""
import argparse
import json
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'readme-to-nixos'
parser = argparse.ArgumentParser()
parser.add_argument('--control', action='append', help='Run only named control(s).')
args = parser.parse_args()
reference = (TASK / 'solution/deployment.nix').read_text()
# Alternate deploys the renderer through the Python environment rather than the
# unit PATH. This is intentionally accepted as a different packaging choice.
alternate = reference.replace(
    '  python = pkgs.python3.withPackages (ps: [ ps.psycopg ps.redis ]);',
    '''  pythonBase = pkgs.python3.withPackages (ps: [ ps.psycopg ps.redis ]);
  python = pkgs.runCommand "docmill-python-with-renderer" { nativeBuildInputs = [ pkgs.makeWrapper ]; } ''
    mkdir -p $out/bin
    makeWrapper ${pythonBase}/bin/python $out/bin/python --prefix PATH : ${pkgs.graphviz}/bin
  '';''').replace('    path = [ pkgs.graphviz ];', '    path = [];')
controls = {
    'canonical': (reference, True),
    'alternative-renderer-wrapper': (alternate, True),
    'empty-deployment': ((TASK / 'deployment.nix').read_text(), False),
    'missing-renderer': (reference.replace('    path = [ pkgs.graphviz ];', '    path = [];'), False),
    'no-worker-at-boot': (reference.replace('  systemd.services.docmill-worker = role "worker";',
                                          '  systemd.services.docmill-worker = (role "worker") // { wantedBy = []; };'), False),
    'ephemeral-report-storage': (reference.replace('/var/lib/docmill/reports', '/run/docmill-reports'), False),
    'no-worker-supervision': (reference.replace('  systemd.services.docmill-worker = role "worker";', '  systemd.services.docmill-worker = pkgs.lib.recursiveUpdate (role "worker") { serviceConfig.Restart = "no"; };'), False),
}
if args.control:
    unknown = set(args.control) - controls.keys()
    if unknown:
        parser.error('unknown controls: ' + ', '.join(sorted(unknown)))
    controls = {name: controls[name] for name in args.control}
logs_root = ROOT / 'logs/readme-to-nixos'
logs = logs_root / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
logs.mkdir(parents=True)
snapshot = logs / 'task-snapshot'
shutil.copytree(TASK, snapshot, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.venv', '.local'))
manifest = {str(p.relative_to(snapshot)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(snapshot.rglob('*')) if p.is_file()}
(logs / 'source-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print('Validation directory: ' + str(logs), flush=True)
results = []
for name, (source, expected) in controls.items():
    candidate = logs / (name + '.nix')
    candidate.write_text(source)
    command = ['nix-build', str(snapshot), '--argstr', 'moduleFile', str(candidate),
               '--no-out-link', '--max-jobs', '1', '--cores', '2']
    started = time.monotonic()
    with (logs / (name + '.log')).open('w') as output:
        proc = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=3600)
    passed = proc.returncode == 0
    phases = {
        'empty-deployment': 'fresh alpha boot, runtime credential, and authenticated report',
        'missing-renderer': 'fresh alpha boot, runtime credential, and authenticated report',
        'no-worker-at-boot': 'fresh alpha boot, runtime credential, and authenticated report',
        'ephemeral-report-storage': 'full guest reboot preserves original data and reports',
        'no-worker-supervision': 'supervisor replaces a killed worker',
    }
    log_text = (logs / (name + '.log')).read_text()
    semantic_failure = expected or ('!!! Test "' + phases[name] + '" failed') in log_text
    item = dict(control=name, expected_pass=expected, passed=passed,
                result_store_path=next((line.strip() for line in reversed(log_text.splitlines()) if line.startswith('/nix/store/') and not line.endswith('.drv')), None) if passed else None,
                failure_in_expected_phase=semantic_failure if not expected else None,
                expectation_met=(passed == expected and semantic_failure), wall_seconds=round(time.monotonic()-started, 2))
    results.append(item)
    print(json.dumps(item), flush=True)
    (logs / (name + '.json')).write_text(json.dumps(item, indent=2)+'\n')
    if not item['expectation_met']:
        print((logs / (name + '.log')).read_text()[-5000:])
(logs / 'validation.json').write_text(json.dumps(results, indent=2)+'\n')
(logs_root / 'latest-validation.json').write_text(json.dumps({'directory': str(logs.relative_to(ROOT)), 'results': results}, indent=2)+'\n')
raise SystemExit(0 if all(r['expectation_met'] for r in results) else 1)

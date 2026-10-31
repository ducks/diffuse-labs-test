"""Validate visual-task controls on native Linux/KVM without model calls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT/'hyprland-visual'
parser = argparse.ArgumentParser()
parser.add_argument('--control', action='append')
args = parser.parse_args()
controls = {
    'canonical': (True, None),
    'alternate-master-layout': (True, None),
    'starting-desktop': (False, 'all visual regions match supplied targets'),
    'wrong-palette': (False, 'all visual regions match supplied targets'),
    'wrong-active-border': (False, 'all visual regions match supplied targets'),
    'missing-terminal-shortcut': (False, 'launcher, terminal, close, keyboard, and workspace are functional'),
    'missing-launcher-shortcut': (False, 'fresh desktop and three visual scenes'),
}
if args.control:
    unknown = set(args.control)-controls.keys()
    if unknown:
        parser.error('Unknown controls: '+', '.join(sorted(unknown)))
    controls = {name: controls[name] for name in args.control}
logs = ROOT/'logs/hyprland-visual'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
logs.mkdir(parents=True)
snapshot = logs/'task-snapshot'
shutil.copytree(TASK, snapshot, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
manifest = {str(p.relative_to(snapshot)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(snapshot.rglob('*')) if p.is_file()}
(logs/'source-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print('Validation directory: '+str(logs), flush=True)
results = []
for name, (expected, phase) in controls.items():
    candidate = logs/name
    source = snapshot/('config' if name == 'starting-desktop' else 'solution/config')
    shutil.copytree(source, candidate)
    hypr = candidate/'hypr/hyprland.lua'
    text = hypr.read_text()
    if name == 'alternate-master-layout':
        text = text.replace('layout="dwindle"', 'layout="master"')
        text = text.replace('  decoration=', '  master={mfact=0.5,orientation="left",new_status="slave"},\n  decoration=')
    elif name == 'wrong-active-border':
        text = text.replace('active_border="rgb(d79921)"', 'active_border="rgb(0088ff)"')
    elif name == 'missing-terminal-shortcut':
        text = text.replace('hl.bind("SUPER + Return", hl.dsp.exec_cmd("desktop-terminal"))', '')
    elif name == 'missing-launcher-shortcut':
        text = text.replace('hl.bind("SUPER + Space", hl.dsp.exec_cmd("desktop-launcher"))', '')
    hypr.write_text(text)
    if name == 'wrong-palette':
        for path in candidate.rglob('*'):
            if path.is_file():
                path.write_text(path.read_text().replace('282828', '102a43'))
    start = time.monotonic()
    with (logs/(name+'.log')).open('w') as stdout:
        proc = subprocess.run(['nix-build', str(snapshot), '--argstr', 'configDir', str(candidate),
                               '--no-out-link', '--max-jobs', '1', '--cores', '2'],
                              stdout=stdout, stderr=subprocess.STDOUT, timeout=900)
    passed = proc.returncode == 0
    log = (logs/(name+'.log')).read_text()
    semantic = None if expected else f'!!! Test "{phase}" failed' in log
    store = next((line for line in reversed(log.splitlines()) if line.startswith('/nix/store/') and not line.endswith('.drv')), None) if passed else None
    item = {'control':name, 'expected_pass':expected, 'passed':passed,
            'failure_in_expected_phase':semantic, 'expectation_met': passed == expected and (expected or semantic),
            'wall_seconds':round(time.monotonic()-start, 2), 'result_store_path':store}
    if passed:
        item['verification'] = json.loads((Path(store)/'result.json').read_text())
    results.append(item)
    print(json.dumps(item), flush=True)
    if not item['expectation_met']:
        print(log[-3500:], flush=True)
    (logs/(name+'.json')).write_text(json.dumps(item, indent=2)+'\n')
record = {'directory':str(logs.relative_to(ROOT)), 'results':results}
(logs/'validation.json').write_text(json.dumps(record, indent=2)+'\n')
(ROOT/'logs/hyprland-visual/latest-validation.json').write_text(json.dumps(record, indent=2)+'\n')
raise SystemExit(0 if all(r['expectation_met'] for r in results) else 1)

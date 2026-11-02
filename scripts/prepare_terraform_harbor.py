"""Build/load public-only Nix and Harbor images; requires Linux/KVM, Nix, Docker."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--rebuild-base', action='store_true')
args = parser.parse_args()
assert (ROOT/'terraform-k8s/default.nix').read_bytes() == (ROOT/'terraform-k8s/tests/default.nix').read_bytes(), 'Native and Harbor verifier expressions must match'
run = ROOT/'logs/terraform-k8s'/('harbor-image-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
run.mkdir(parents=True)
workspace = run/'context/workspace'
subprocess.run(['python3', str(ROOT/'scripts/export_terraform_task.py'), str(workspace)], check=True)
assert not any((workspace/name).exists() for name in ['tests', 'solution', 'default.nix'])
base = subprocess.run(['docker', 'image', 'inspect', 'diffuse-terraform-pilot:001'], capture_output=True)
if args.rebuild_base or base.returncode:
    with (run/'base-build.log').open('w') as log:
        result = subprocess.run(['nix-build', str(ROOT/'terraform-k8s/environment/base-image.nix'),
            '--argstr', 'workspace', str(workspace), '--no-out-link', '--max-jobs', '1', '--cores', '2'],
            stdout=log, stderr=subprocess.STDOUT, check=True)
    archive = next(line for line in reversed((run/'base-build.log').read_text().splitlines()) if line.startswith('/nix/store/'))
    subprocess.run(['docker', 'load', '-i', archive], check=True)
shutil.copyfile(ROOT/'terraform-k8s/environment/Dockerfile', run/'context/Dockerfile')
subprocess.run(['docker', 'build', '-t', 'diffuse-terraform-harbor:v1', str(run/'context')], check=True)
image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', 'diffuse-terraform-harbor:v1'], text=True))[0]
record = {'image':'diffuse-terraform-harbor:v1', 'image_id': image['Id'],
          'public_manifest':{str(p.relative_to(workspace)):hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted(workspace.rglob('*')) if p.is_file()},
          'no_tests_or_solution_in_agent_image':True}
(run/'summary.json').write_text(json.dumps(record,indent=2)+'\n')
print('Image record: '+str(run/'summary.json'))

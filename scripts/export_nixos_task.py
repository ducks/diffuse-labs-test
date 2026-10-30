"""Export only the public task workspace; never includes verifier or oracle."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'readme-to-nixos'
parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path, help='New directory for the public workspace.')
args = parser.parse_args()
output = args.output.resolve()
if output.exists():
    parser.error('output already exists; choose a new directory')
output.mkdir(parents=True)
for name in ['instruction.md', 'deployment.nix', 'nixpkgs.nix', 'source.nix', 'vm.nix']:
    shutil.copyfile(TASK / name, output / name)
shutil.copytree(TASK / 'repository', output / 'repository',
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.venv', '.local', '.git'))
print(output)

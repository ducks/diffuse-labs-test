"""Export the public Terraform/K3s workspace without reference or private tests."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'terraform-k8s'
parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path)
args = parser.parse_args()
output = args.output.resolve()
if output.exists():
    parser.error('output exists; choose a new directory')
output.mkdir(parents=True)
for name in ['instruction.md', 'nixpkgs.nix', 'toolchain.nix', 'images.nix',
             'base.nix', 'vm.nix', 'shell.nix']:
    shutil.copyfile(TASK / name, output / name)
for name in ['deployment', 'repository']:
    shutil.copytree(TASK / name, output / name,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.venv', '.git'))
print(output)

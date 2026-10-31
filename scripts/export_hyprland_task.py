"""Export only the public visual task; excludes private tests and reference."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'hyprland-visual'
parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path)
args = parser.parse_args()
output = args.output.resolve()
if output.exists():
    parser.error('output exists; choose a new directory')
if not all((TASK/'targets'/name).is_file() for name in ['empty.png', 'tiled.png', 'launcher.png']):
    parser.error('validated target captures have not been installed')
output.mkdir(parents=True)
for name in ['instruction.md', 'nixpkgs.nix', 'base.nix', 'vm.nix', 'preview.nix', 'capture.py']:
    shutil.copyfile(TASK/name, output/name)
for name in ['config', 'targets']:
    shutil.copytree(TASK/name, output/name)
print(output)

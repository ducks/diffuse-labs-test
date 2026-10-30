import importlib.util
import os
from pathlib import Path
import sys

sys.path.insert(0, os.environ.get('SERVICE_DIR', '/opt/task-service'))
candidate = Path(os.environ.get('CANDIDATE_DIR', '/app'))
spec = importlib.util.spec_from_file_location('candidate_repair', candidate / 'repair.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.repair(Path(sys.argv[1]))

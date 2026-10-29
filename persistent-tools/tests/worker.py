"""Fresh-session driver and deterministic crash-test worker."""
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, os.environ.get('SERVICE_DIR', '/opt/task-service'))
spec = importlib.util.spec_from_file_location('candidate', os.environ.get('STORE_PATH', '/app/store.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
request = json.loads(sys.stdin.readline())
try:
    store = module.ToolStore(Path(sys.argv[1]))
    action = request.pop('action')
    if action == 'list':
        value = store.list_tools()
    elif action == 'promote':
        value = store.promote(request['name'], request['source'], request['cases'])
    elif action == 'call':
        value = store.call(request['name'], request['input'])
    else:
        raise ValueError('unknown action')
    print(json.dumps({'ok': True, 'value': value}), flush=True)
except Exception as error:
    print(json.dumps({'ok': False, 'error': type(error).__name__}), flush=True)

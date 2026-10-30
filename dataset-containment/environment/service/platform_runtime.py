"""Public deployment control: restart only the worker, with persisted config."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request


def read_settings(root):
    path = Path(root) / 'etc/dataset-platform/worker.env'
    return dict(line.split('=', 1) for line in path.read_text().splitlines()
                if line and not line.startswith('#'))


def stop_worker(root):
    root = Path(root)
    path = root / 'run/worker.pid'
    if not path.exists():
        return
    pid = int(path.read_text())
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            stat = Path('/proc') / str(pid) / 'stat'
            if not stat.exists() or stat.read_text().rsplit(')', 1)[1].split()[0] == 'Z':
                return
        except FileNotFoundError:
            return
        time.sleep(.02)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def restart_worker(root):
    """Do not restart API, identity, output, or scheduler services."""
    root = Path(root)
    stop_worker(root)
    deployment = json.loads((root / 'run/deployment.json').read_text())
    settings = read_settings(root)
    # The worker gets its explicit service configuration, not host credentials.
    env = {'PATH': os.defpath, 'PYTHONPATH': str(Path(__file__).resolve().parent), **settings}
    with (root / 'run/worker.log').open('ab') as log:
        process = subprocess.Popen([sys.executable, deployment['worker_source'], 'worker'],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=env,
            start_new_session=True)
    (root / 'run/worker.pid').write_text(str(process.pid))
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('worker exited; inspect run/worker.log')
        try:
            with urllib.request.urlopen('http://127.0.0.1:' + settings['PORT'] + '/health', timeout=.2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(.02)
    stop_worker(root)
    raise RuntimeError('worker did not become ready')

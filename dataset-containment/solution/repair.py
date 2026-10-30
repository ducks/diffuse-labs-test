"""Contain the exposed worker identity and persist the repaired deployment."""
import json
import os
from pathlib import Path
import secrets
import sqlite3
from platform_service import issue
from platform_runtime import restart_worker


def repair(root):
    root = Path(root)
    with sqlite3.connect(root / 'var/lib/dataset-identity/auth.sqlite3', timeout=10) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute("UPDATE credentials SET active=0 WHERE principal='worker'")
        replacement = {kind: issue(db, 'worker', kind) for kind in ('access', 'refresh')}
    identity = root / 'var/lib/dataset-worker/identity.json'
    staged = identity.with_suffix('.next')
    staged.write_text(json.dumps(replacement))
    staged.chmod(0o600)
    os.replace(staged, identity)
    with sqlite3.connect(root / 'var/lib/dataset-api/state.sqlite3', timeout=10) as db:
        db.execute("UPDATE schedules SET active=0 WHERE owner='worker' AND kind='dataset-export'")
    config = root / 'etc/dataset-platform/worker.env'
    settings = dict(line.split('=', 1) for line in config.read_text().splitlines() if line)
    settings['ALLOWED_ROOT'] = str(root / 'var/lib/dataset-worker/incoming')
    settings['PAUSED'] = '0'
    config.write_text(''.join(key + '=' + value + '\n' for key, value in settings.items()))
    restart_worker(root)

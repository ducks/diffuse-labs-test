"""Contain a provisioned deployment without replacing accepted work."""
import json
import os
from pathlib import Path
import sys

# Also support callers that import this submission without setting PYTHONPATH.
if '/opt/task-service' not in sys.path:
    sys.path.insert(0, '/opt/task-service')
from platform_runtime import read_settings, restart_worker, stop_worker
from platform_service import database, issue


def atomic_write(path, text, mode=None):
    path = Path(path)
    stat = path.stat()
    temporary = path.with_name(path.name + '.repair-tmp')
    try:
        temporary.write_text(text)
        os.chmod(temporary, mode if mode is not None else stat.st_mode & 0o777)
        os.chown(temporary, stat.st_uid, stat.st_gid)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def repair(root):
    root = Path(root)
    settings = read_settings(root)
    identity_db = root / 'var/lib/dataset-identity/auth.sqlite3'
    api_db = root / 'var/lib/dataset-api/state.sqlite3'
    access_file = Path(settings['ACCESS_FILE'])
    inputs = Path(settings['INPUT_DIR']).resolve(strict=True)
    # Inspect the identity being replaced before making any changes.
    old_identity = json.loads(access_file.read_text())
    if not isinstance(old_identity.get('access'), str):
        raise ValueError('worker access credential missing')
    stop_worker(root)
    # Serialize against refresh issuance. All worker access tokens, including
    # those minted from the exposed refresh token, belong to this principal.
    with database(identity_db) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute("UPDATE credentials SET active=0 WHERE principal='worker'")
        replacement = {'access': issue(db, 'worker', 'access')}
    atomic_write(access_file, json.dumps(replacement) + '\n', 0o600)
    with database(api_db) as db:
        db.execute("UPDATE schedules SET active=0 WHERE owner='worker' AND kind='dataset-export'")
    settings['ALLOWED_ROOT'] = str(inputs)
    settings['PAUSED'] = '0'
    atomic_write(root / 'etc/dataset-platform/worker.env',
                 ''.join(key + '=' + value + '\n' for key, value in settings.items()))
    # The fixed worker reconciles both queued and retry jobs against durable
    # receipts, using the public acknowledgement endpoint for every completion.
    restart_worker(root)

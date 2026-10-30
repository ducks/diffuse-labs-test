"""Contain a provisioned deployment while retaining its accepted work."""
import json
import os
from pathlib import Path
import secrets
import sqlite3
import hashlib

from platform_runtime import read_settings, stop_worker, restart_worker


def atomic_write(path, text, mode=None):
    path = Path(path)
    temporary = path.with_name(path.name + '.repair-' + secrets.token_hex(8))
    stat = path.stat()
    try:
        temporary.write_text(text)
        temporary.chmod(mode if mode is not None else stat.st_mode & 0o777)
        if os.geteuid() == 0:
            os.chown(temporary, stat.st_uid, stat.st_gid)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def repair(root):
    root = Path(root)
    settings = read_settings(root)
    auth_path = root / 'var/lib/dataset-identity/auth.sqlite3'
    api_path = root / 'var/lib/dataset-api/state.sqlite3'
    # Inspect the live deployment before selecting the containment scope.
    with sqlite3.connect(auth_path, timeout=10) as db:
        worker_credentials = db.execute(
            "SELECT id,kind FROM credentials WHERE principal='worker'").fetchall()
    with sqlite3.connect(api_path, timeout=10) as db:
        exports = db.execute(
            "SELECT id FROM schedules WHERE owner='worker' AND kind='dataset-export' AND active=1").fetchall()
    identity_path = Path(settings['ACCESS_FILE'])
    json.loads(identity_path.read_text())
    Path(settings['INPUT_DIR']).resolve(strict=True)

    # Only the worker is stopped. Core services continue accepting client work.
    stop_worker(root)
    try:
        replacement = {}
        with sqlite3.connect(auth_path, timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            # Include every descendant minted from a disclosed refresh token,
            # including credentials created since the inspection above.
            db.execute("UPDATE credentials SET active=0 WHERE principal='worker'")
            for kind in ('access', 'refresh'):
                token = secrets.token_hex(32)
                db.execute('INSERT INTO credentials VALUES (?,?,?,?,1)',
                           (secrets.token_hex(16), hashlib.sha256(token.encode()).hexdigest(),
                            'worker', kind))
                replacement[kind] = token
        atomic_write(identity_path, json.dumps(replacement)+'\n', 0o600)
        with sqlite3.connect(api_path, timeout=10) as db:
            db.execute("UPDATE schedules SET active=0 WHERE owner='worker' AND kind='dataset-export'")
        settings['ALLOWED_ROOT'] = settings['INPUT_DIR']
        settings['PAUSED'] = '0'
        atomic_write(root / 'etc/dataset-platform/worker.env',
                     ''.join(key+'='+value+'\n' for key,value in settings.items()))
    finally:
        restart_worker(root)

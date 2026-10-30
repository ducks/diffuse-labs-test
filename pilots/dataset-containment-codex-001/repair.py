"""Contain a provisioned deployment while retaining its accepted work."""
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3

from platform_runtime import read_settings, restart_worker, stop_worker


def repair(root):
    root = Path(root)
    settings = read_settings(root)
    auth_path = root / 'var/lib/dataset-identity/auth.sqlite3'
    api_path = root / 'var/lib/dataset-api/state.sqlite3'
    credential_path = Path(settings['ACCESS_FILE'])
    credentials = json.loads(credential_path.read_text())

    # Stop the sole publisher before changing its identity. Core servers and
    # client acceptance stay available throughout this short handover.
    stop_worker(root)
    try:
        with sqlite3.connect(auth_path, timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            principals = set()
            for token in credentials.values():
                if not isinstance(token, str):
                    continue
                row = db.execute('SELECT principal FROM credentials WHERE digest=?',
                                 (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
                if row:
                    principals.add(row[0])
            # Worker-derived access tokens share the worker principal, including
            # access minted by refresh; retaining only the two disclosed hashes
            # would leave those descendants valid.
            principals.add('worker')
            for principal in principals:
                if principal == 'worker':
                    db.execute('UPDATE credentials SET active=0 WHERE principal=?', (principal,))
            replacement = {}
            for kind in ('access', 'refresh'):
                token = secrets.token_hex(32)
                db.execute('INSERT INTO credentials VALUES (?,?,?,?,1)',
                           (secrets.token_hex(16), hashlib.sha256(token.encode()).hexdigest(), 'worker', kind))
                replacement[kind] = token
        # Keep the existing inode's permissions and ownership for installations
        # that run the worker under its own service account.
        credential_path.write_text(json.dumps(replacement)+'\n')
        credential_path.chmod(0o600)

        with sqlite3.connect(api_path, timeout=10) as db:
            db.execute("UPDATE schedules SET active=0 WHERE owner='worker' AND kind='dataset-export'")
        settings['ALLOWED_ROOT'] = settings['INPUT_DIR']
        settings['PAUSED'] = '0'
        env_path = root / 'etc/dataset-platform/worker.env'
        env_path.write_text(''.join(key+'='+value+'\n' for key, value in settings.items()))
    finally:
        restart_worker(root)

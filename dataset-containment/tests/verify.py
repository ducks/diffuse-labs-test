"""Black-box deployment repair test with trusted HTTP services and ledgers."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

SERVICE = Path(os.environ.get('SERVICE_DIR', '/opt/task-service')).resolve()
CANDIDATE = Path(os.environ.get('CANDIDATE_DIR', '/app')).resolve()
sys.path.insert(0, str(SERVICE))
import platform_service as app
import platform_runtime as runtime
import provision
import lifecycle as controller


class ContainmentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / 'deployment'
        provision.initialize(self.root)
        self.servers = []
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.addCleanup(self.shutdown)
        self.state_dir = self.base / 'controller'
        self.api_db = self.root / 'var/lib/dataset-api/state.sqlite3'
        self.servers_spec = []
        self.authorized_receipts = {}
        self.start_core()
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            self.worker_port = reserve.getsockname()[1]
        self.worker = 'http://127.0.0.1:' + str(self.worker_port)
        settings = {'PORT': str(self.worker_port), 'API_URL': self.api,
                    'OUTPUT_URL': self.output, 'INPUT_DIR': str(self.root / 'var/lib/dataset-worker/incoming'),
                    'ALLOWED_ROOT': str(self.root), 'PAUSED': '0',
                    'ACCESS_FILE': str(self.root / 'var/lib/dataset-worker/identity.json')}
        (self.root / 'etc/dataset-platform/worker.env').write_text(
            ''.join(key + '=' + value + '\n' for key, value in settings.items()))
        (self.root / 'run').mkdir()
        self.deployment = self.root / 'run/deployment.json'
        # Reproduce the incident using the original worker, independently of
        # the proposed patch. The repair then deploys the candidate's code.
        self.deployment.write_text(json.dumps({'worker_source': str(SERVICE / 'platform_service.py')}))
        runtime.restart_worker(self.root)
        original = controller.request
        def routed(_base, path, payload=None, token=None, timeout=6):
            for prefix, target in [('/identity', self.identity), ('/api', self.api),
                                   ('/outputs', self.output), ('/worker', self.worker)]:
                if path.startswith(prefix + '/'):
                    return original(target, path[len(prefix):], payload, token, timeout=timeout)
            return original(self.api, path, payload, token, timeout=timeout)
        self.stack.enter_context(patch.object(controller, 'request', side_effect=routed))
        self.stack.enter_context(patch.object(controller, 'remote', side_effect=self.guest))
        self.traffic_thread = None
        self.stack.enter_context(patch.object(controller.traffic, 'start', side_effect=self.start_traffic))
        self.addCleanup(self.stop_traffic)
        controller.run('preflight', 'local', self.state_dir)
        self.state = json.loads((self.state_dir / 'response-contract.json').read_text())
        self.deployment.write_text(json.dumps({'worker_source': str(CANDIDATE / 'service.py')}))

    def start_server(self, role, settings, port=0):
        server = app.server(role, port, settings)
        server.RequestHandlerClass.log_message = lambda *args: None
        if role == 'output':
            original_response = server.RequestHandlerClass.respond
            def observe_publication(handler, status, payload):
                if status == 201 and handler.path.startswith('/publish/'):
                    receipt = payload['receipt']
                    with sqlite3.connect(self.root / 'var/lib/dataset-output/receipts.sqlite3', timeout=10) as db:
                        row = db.execute('SELECT job,body FROM receipts WHERE id=?', (receipt,)).fetchone()
                    self.authorized_receipts[receipt] = tuple(row)
                return original_response(handler, status, payload)
            server.RequestHandlerClass.respond = observe_publication
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.servers.append((server, thread))
        self.servers_spec.append((role, settings, server.server_port))
        return 'http://127.0.0.1:' + str(server.server_port)

    def start_core(self):
        self.identity = self.start_server('identity', {
            'DATABASE': str(self.root / 'var/lib/dataset-identity/auth.sqlite3')})
        self.api = self.start_server('api', {'DATABASE': str(self.api_db), 'IDENTITY_URL': self.identity})
        self.output = self.start_server('output', {
            'DATABASE': str(self.root / 'var/lib/dataset-output/receipts.sqlite3'), 'IDENTITY_URL': self.identity})
        self.start_scheduler()

    def start_scheduler(self):
        self.scheduler_stop = threading.Event()
        def schedule():
            while not self.scheduler_stop.is_set():
                app.tick(self.api_db)
                self.scheduler_stop.wait(.1)
        self.scheduler_thread = threading.Thread(target=schedule, daemon=True)
        self.scheduler_thread.start()

    def stop_scheduler(self):
        if hasattr(self, 'scheduler_stop'):
            self.scheduler_stop.set()
            self.scheduler_thread.join(3)

    def shutdown(self):
        if hasattr(self, 'deployment'):
            runtime.stop_worker(self.root)
            # Reap child processes created by this verifier when possible.
            try:
                while os.waitpid(-1, os.WNOHANG)[0]:
                    pass
            except ChildProcessError:
                pass
        self.stop_scheduler()
        for server, thread in self.servers:
            server.shutdown()
            server.server_close()
            thread.join(3)
        self.servers = []

    def restart_all(self):
        specifications = list(self.servers_spec)
        self.shutdown()
        self.servers_spec = []
        for role, settings, port in specifications:
            self.start_server(role, settings, port)
        self.start_scheduler()
        runtime.restart_worker(self.root)

    def guest(self, action, data=None):
        result = json.loads(json.dumps(controller.guest_action(action, data or {}, self.root)))
        if action in ('bootstrap', 'partial'):
            observed = result if action == 'bootstrap' else controller.guest_action('snapshot', {}, self.root)
            for row in observed['receipts']:
                if action == 'bootstrap' or row[2] in data:
                    self.authorized_receipts[row[1]] = (row[2], row[3])
        return result

    def assert_output_provenance(self):
        for row in self.guest('snapshot')['receipts']:
            self.assertEqual(self.authorized_receipts.get(row[1]), (row[2], row[3]),
                             'receipt was not provisioned or published by the output service')

    def start_traffic(self, base, state_dir):
        control = controller.traffic.prepare(state_dir, os.getpid())
        self.traffic_thread = threading.Thread(target=controller.traffic.run,
            args=(base, state_dir, control['nonce']),
            kwargs={'controller': controller, 'interval': .1, 'deadline': 15, 'max_seconds': 90},
            daemon=True)
        self.traffic_thread.start()
        return control

    def stop_traffic(self):
        if self.traffic_thread is not None:
            controller.traffic.stop(self.state_dir, timeout=10)
            self.traffic_thread.join(5)
            self.traffic_thread = None

    def repair(self):
        env = {'PATH': os.defpath, 'SERVICE_DIR': str(SERVICE), 'CANDIDATE_DIR': str(CANDIDATE),
               'PYTHONPATH': str(SERVICE)}
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('run_repair.py')),
                                 str(self.root)], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, 'repair failed:\n' + result.stderr)

    def test_containment_live_recovery_and_service_restarts(self):
        self.repair()
        # These assertions observe HTTP and independent SQLite ledgers, not a
        # repair function's return value or the worker's success messages.
        controller.run('immediate', 'local', self.state_dir)
        self.stop_traffic()
        self.restart_all()
        controller.run('service-restart', 'local', self.state_dir)
        self.restart_all()
        controller.run('second-service-restart', 'local', self.state_dir)
        self.assert_output_provenance()

    def test_lost_acknowledgement_and_same_job_replay(self):
        self.repair()
        controller.run('immediate', 'local', self.state_dir)
        self.stop_traffic()
        # Hold one queue acknowledgement after the output service has committed
        # its receipt. This seam is an explicit handler event, not a timed kill.
        api_server = next(server for server, _ in self.servers if server.server_port == int(self.api.rsplit(':', 1)[-1]))
        handler = api_server.RequestHandlerClass
        original = handler.handle_request
        dropped = threading.Event()
        target = secrets.token_hex(16)
        def lose_once(instance, method):
            if instance.path == '/internal/complete/' + target and not dropped.is_set():
                dropped.set()
                return instance.respond(503, {'error': 'acknowledgement interrupted'})
            return original(instance, method)
        content = 'key,value\n' + secrets.token_hex(16) + ',7\n'
        manifest = self.guest('inputs', {target: content})[target]
        record = {target: {'body': manifest, 'result': app.preview_result(content.encode())}}
        with patch.object(handler, 'handle_request', lose_once):
            controller.http('local', '/api/jobs/' + target, manifest, self.state['client']['access'], 202)
            self.assertTrue(dropped.wait(5), 'worker never reached acknowledgement boundary')
            controller.wait_jobs({'records': record}, timeout=10)
        controller.receipts_ok(record, self.guest('snapshot'))
        # Re-present a previously acknowledged job as retry: it must adopt the
        # original receipt instead of publishing another external effect.
        with sqlite3.connect(self.api_db, timeout=10) as db:
            db.execute("UPDATE jobs SET state='retry',completions=0 WHERE id=?", (target,))
        controller.wait_jobs({'records': record}, timeout=10)
        controller.receipts_ok(record, self.guest('snapshot'))
        self.assert_output_provenance()


if __name__ == '__main__':
    unittest.main(verbosity=2)

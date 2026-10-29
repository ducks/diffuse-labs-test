"""Independent behavioral checks. Never import code from the submitted runner."""
import json
import os
from pathlib import Path
import selectors
import sqlite3
import subprocess
import sys
import tempfile
import unittest

RUNNER = Path(os.environ.get("RUNNER", "/app/runner.py")).resolve()
SERVICE = Path(os.environ.get("SERVICE_DIR", "/opt/task-service")).resolve()


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.session = self.root / "session.json"
        self.store = self.root / "external.sqlite"
        self.plan = [
            {"name": "deploy", "arguments": {"service": "billing", "version": "r17"}},
            {"name": "notify", "arguments": {"channel": "ops", "message": "ready"}},
            {"name": "deploy", "arguments": {"service": "worker", "version": "r19"}},
        ]
        self.plan_path = self.root / "plan.json"
        self.plan_path.write_text(json.dumps(self.plan))

    def launch(self, barrier=None, session=None, session_id="customer-A"):
        env = os.environ.copy()
        env.pop("RECOVERY_BARRIER", None)
        env["PYTHONPATH"] = str(SERVICE)
        if barrier:
            env["RECOVERY_BARRIER"] = barrier
        return subprocess.Popen([
            sys.executable, str(RUNNER), "--session", str(session or self.session),
            "--store", str(self.store), "--plan", str(self.plan_path),
            "--session-id", session_id,
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True, cwd=self.root)

    def finish(self, **kwargs):
        proc = self.launch(**kwargs)
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self.fail("runner did not finish")
        self.assertEqual(proc.returncode, 0, (out, err))

    def interrupt(self, stage, index):
        proc = self.launch(f"{stage}:{index}")
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=10), "checkpoint handshake absent")
            line = proc.stdout.readline()
            self.assertEqual(json.loads(line), {"checkpoint": stage, "index": index})
            before = json.loads(self.session.read_text())
            proc.kill()  # SIGKILL, so finally/atexit handlers cannot save the session.
            proc.communicate(timeout=5)
            return before
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.communicate()

    def effects(self):
        if not self.store.exists():
            return []
        with sqlite3.connect(self.store) as db:
            return [json.loads(row[0]) for row in db.execute(
                "SELECT receipt FROM effects ORDER BY seq")]

    def assert_complete(self, session=None, session_id="customer-A", receipts=None):
        state = json.loads((session or self.session).read_text())
        self.assertEqual(state["session_id"], session_id)
        self.assertEqual(state["next"], len(self.plan))
        messages = state["messages"]
        self.assertEqual(messages[0], {"role": "user", "content": "Execute the release plan."})
        self.assertEqual(len(messages), 2 * len(self.plan) + 2)
        self.assertEqual(messages[-1], {"role": "assistant", "content": "Done"})
        receipts = receipts if receipts is not None else self.effects()
        self.assertEqual(len(receipts), len(self.plan), "side effects repeated or missing")
        ids = set()
        for i, (action, receipt) in enumerate(zip(self.plan, receipts)):
            call, result = messages[1 + 2*i:3 + 2*i]
            self.assertEqual(call["role"], "tool_call")
            self.assertNotIn(call["id"], ids)
            ids.add(call["id"])
            self.assertEqual(call["name"], action["name"])
            self.assertEqual(call["arguments"], action["arguments"])
            self.assertEqual(receipt["name"], action["name"])
            self.assertEqual(receipt["arguments"], action["arguments"])
            self.assertEqual(receipt["operation_id"], call["id"])
            self.assertEqual(result, {"role": "tool_result", "call_id": call["id"],
                                      "result": receipt})

    def test_clean_and_completed_resume(self):
        self.finish()
        self.assert_complete()
        saved = self.session.read_bytes()
        self.finish()
        self.assertEqual(self.session.read_bytes(), saved, "completed history changed")
        self.assert_complete()

    def test_crash_boundaries(self):
        # Separate stores ensure every action/boundary is reached from a fresh run.
        for stage in ("before_effect", "after_effect", "after_save"):
            for index in range(len(self.plan)):
                with self.subTest(stage=stage, index=index):
                    self.session.unlink(missing_ok=True)
                    self.store.unlink(missing_ok=True)
                    before = self.interrupt(stage, index)
                    self.finish()
                    self.assert_complete()
                    recovered = json.loads(self.session.read_text())
                    self.assertEqual(recovered["messages"][:len(before["messages"])],
                                     before["messages"], "persisted history was rewritten")

    def test_repeated_crashes(self):
        before = self.interrupt("after_effect", 0)
        self.interrupt("after_save", 0)
        self.interrupt("after_effect", 1)
        self.interrupt("before_effect", 2)
        self.finish()
        self.assert_complete()
        state = json.loads(self.session.read_text())
        self.assertEqual(state["messages"][:len(before["messages"])], before["messages"])

    def test_distinct_sessions_share_service(self):
        self.finish()
        first = self.effects()
        other = self.root / "other.json"
        self.finish(session=other, session_id="customer-B")
        all_effects = self.effects()
        self.assertEqual(len(all_effects), 2 * len(self.plan))
        self.assert_complete(receipts=first)
        self.assert_complete(session=other, session_id="customer-B",
                             receipts=all_effects[len(self.plan):])

    def test_corrupt_state_is_not_overwritten(self):
        damaged = b'{"session_id": "customer-A", "messages": ['
        self.session.write_bytes(damaged)
        proc = self.launch()
        try:
            proc.communicate(timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.session.read_bytes(), damaged)
        self.assertEqual(self.effects(), [])

    def test_wrong_session_id_is_rejected(self):
        self.finish()
        saved = self.session.read_bytes()
        proc = self.launch(session_id="wrong-customer")
        proc.communicate(timeout=10)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.session.read_bytes(), saved)
        self.assert_complete()

    def test_empty_plan(self):
        self.plan = []
        self.plan_path.write_text("[]")
        self.finish()
        self.assert_complete()
        saved = self.session.read_bytes()
        self.finish()
        self.assertEqual(self.session.read_bytes(), saved)


if __name__ == "__main__":
    unittest.main(verbosity=2)

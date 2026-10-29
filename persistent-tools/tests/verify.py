"""Behavioral verification; no access to the oracle or source-shape grading."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time
import unittest

SERVICE = os.environ.get('SERVICE_DIR', '/opt/task-service')
CANDIDATE = os.environ.get('STORE_PATH', '/app/store.py')
sys.path.insert(0, SERVICE)
from tool_runtime import MAX_BYTES, ToolError, execute

spec = importlib.util.spec_from_file_location('candidate', CANDIDATE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
WORKER = Path(__file__).with_name('worker.py')


def program(expression):
    return 'import json, sys\nx = json.load(sys.stdin)\nprint(json.dumps(' + expression + '))\n'


V1 = program("{'words': x['text'].split(), 'count': len(x['text'].split())}")
V2 = program("{'words': x['text'].upper().split(), 'count': len(x['text'].split())}")
CASE1 = [{'input': {'text': 'one two'}, 'expected': {'words': ['one', 'two'], 'count': 2}}]
CASE2 = [{'input': {'text': 'one two'}, 'expected': {'words': ['ONE', 'TWO'], 'count': 2}}]


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'store'
        self.store = module.ToolStore(self.root)

    def seed(self):
        return self.store.promote('word_count', V1, CASE1)

    def fresh(self, request):
        env = dict(os.environ, SERVICE_DIR=SERVICE, STORE_PATH=CANDIDATE)
        env.pop('TOOLSTORE_FAULT', None)
        proc = subprocess.run([sys.executable, str(WORKER), str(self.root)],
                              input=json.dumps(request) + '\n', capture_output=True,
                              text=True, env=env, timeout=5)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def assert_v1(self):
        self.assertEqual(module.ToolStore(self.root).call('word_count', {'text': '  a b c '}),
                         {'words': ['a', 'b', 'c'], 'count': 3})

    def test_saved_artifact_survives_fresh_process(self):
        digest = self.seed()
        self.assertEqual(digest, hashlib.sha256(V1.encode()).hexdigest())
        self.assertEqual(self.fresh({'action': 'list'}),
                         {'ok': True, 'value': {'word_count': digest}})
        self.assertEqual(self.fresh({'action': 'call', 'name': 'word_count',
                                    'input': {'text': ' later session works '}}),
                         {'ok': True, 'value': {'words': ['later', 'session', 'works'], 'count': 3}})

    def test_multiple_tools_and_independent_versions(self):
        self.seed()
        for name, expression, value, expected in [
            ('sort_values', 'sorted(x)', [3, 1, 2], [1, 2, 3]),
            ('invert-map', '{v: k for k, v in x.items()}', {'a': 'b'}, {'b': 'a'}),
            ('Length2', 'len(x)', [1, 2, 3], 3),
        ]:
            self.store.promote(name, program(expression), [{'input': value, 'expected': expected}])
            self.assertEqual(self.fresh({'action': 'call', 'name': name, 'input': value})['value'], expected)
        self.store.promote('word_count', V2, CASE2)
        self.assertEqual(len(self.store.list_tools()), 4)
        self.assertEqual(self.store.call('word_count', {'text': 'a b'})['words'], ['A', 'B'])
        self.assertEqual(self.store.call('sort_values', [8, 4]), [4, 8])

    def test_failed_candidates_preserve_prior_version(self):
        self.seed()
        failures = [
            ('bad syntax !', CASE1),
            (program('None'), CASE1),
            ('raise RuntimeError("broken")', CASE1),
            ('print("not json")', CASE1),
            ('print("NaN")', CASE1),
            ('print("1\\n2")', CASE1),
            ('while True: pass', CASE1),
            ('import sys\nsys.stdout.write("x" * 1000000)', CASE1),
        ]
        for source, cases in failures:
            with self.subTest(source=source):
                with self.assertRaises(ToolError):
                    self.store.promote('word_count', source, cases)
                self.assert_v1()

    def test_all_validation_cases_are_checked(self):
        self.seed()
        cases = CASE2 + [{'input': {'text': 'a'}, 'expected': {'words': ['WRONG'], 'count': 1}}]
        with self.assertRaises(ToolError):
            self.store.promote('word_count', V2, cases)
        self.assert_v1()

    def test_failed_new_tool_is_not_discoverable(self):
        with self.assertRaises(ToolError):
            self.store.promote('bad_tool', program('0'), [{'input': 0, 'expected': 1}])
        self.assertEqual(self.fresh({'action': 'list'})['value'], {})

    def test_name_and_source_bounds_before_writing(self):
        outside = Path(self.temp.name) / 'escape.py'
        outside.write_text('untouched')
        for name in ['../escape', '/tmp/escape', '', '1tool', 'a/b', 'a' * 49, 'écho']:
            with self.subTest(name=name), self.assertRaises(ToolError):
                self.store.promote(name, V1, CASE1)
        self.assertEqual(outside.read_text(), 'untouched')
        for source in ['', 'x' * (MAX_BYTES + 1), None]:
            with self.assertRaises(ToolError):
                self.store.promote('okay', source, CASE1)
        self.assertEqual(self.store.list_tools(), {})

    def test_invalid_case_sets_do_not_publish(self):
        self.seed()
        for cases in [[], CASE1 * 33, None, [{}], [{'input': 1}],
                      [{'input': float('nan'), 'expected': None}]]:
            with self.subTest(cases=cases), self.assertRaises(ToolError):
                self.store.promote('word_count', V2, cases)
            self.assert_v1()

    def test_unknown_tool_fails_without_mutation(self):
        self.seed()
        before = self.store.list_tools()
        with self.assertRaises(ToolError):
            self.store.call('unknown', {})
        self.assertEqual(self.store.list_tools(), before)

    def test_execution_failures_are_not_reported_as_success(self):
        source = program("x['value']")
        self.store.promote('lookup', source, [{'input': {'value': 1}, 'expected': 1}])
        with self.assertRaises(ToolError):
            self.store.call('lookup', {})
        with self.assertRaises(ToolError):
            self.store.call('lookup', {'value': 'x' * (MAX_BYTES + 1)})

    def test_corrupt_manifest_not_silently_replaced(self):
        self.seed()
        path = self.root / 'active.json'
        for raw in [b'{bad json', b'[]', b'{"word_count":"../../escape"}']:
            path.write_bytes(raw)
            with self.assertRaises(ToolError):
                module.ToolStore(self.root).list_tools()
            with self.assertRaises(ToolError):
                module.ToolStore(self.root).promote('other', V1, CASE1)
            self.assertEqual(path.read_bytes(), raw)

    def test_missing_or_corrupt_artifact_fails_clearly(self):
        digest = self.seed()
        path = self.root / 'blobs' / (digest + '.py')
        path.write_text(program('None'))
        with self.assertRaises(ToolError):
            self.store.call('word_count', {})
        path.unlink()
        with self.assertRaises(ToolError):
            self.store.list_tools()

    def test_fresh_process_promotes_without_losing_existing_names(self):
        self.seed()
        result = self.fresh({'action': 'promote', 'name': 'count_chars',
                            'source': program('len(x)'),
                            'cases': [{'input': 'abc', 'expected': 3}]})
        self.assertTrue(result['ok'], result)
        self.assert_v1()
        self.assertEqual(set(self.store.list_tools()), {'word_count', 'count_chars'})

    def test_candidate_source_is_copied_not_referenced(self):
        original = Path(self.temp.name) / 'generated.py'
        original.write_text(V1)
        self.store.promote('word_count', original.read_text(), CASE1)
        original.unlink()
        self.assert_v1()

    def test_crashes_never_publish_partial_or_unvalidated_versions(self):
        self.seed()
        for point in ['staged', 'validated', 'before-publish', 'published']:
            with self.subTest(point=point):
                self.store.promote('word_count', V1, CASE1)
                env = dict(os.environ, SERVICE_DIR=SERVICE, STORE_PATH=CANDIDATE,
                           TOOLSTORE_FAULT=point)
                proc = subprocess.Popen([sys.executable, str(WORKER), str(self.root)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, env=env)
                try:
                    proc.stdin.write(json.dumps({'action': 'promote', 'name': 'word_count',
                                                 'source': V2, 'cases': CASE2}) + '\n')
                    proc.stdin.flush()
                    with selectors.DefaultSelector() as selector:
                        selector.register(proc.stdout, selectors.EVENT_READ)
                        self.assertTrue(selector.select(5), 'worker did not reach fault barrier')
                        self.assertEqual(proc.stdout.readline().strip(), 'BARRIER:' + point)
                    proc.kill()
                    proc.wait(timeout=3)
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait(timeout=3)
                    proc.stdin.close()
                    proc.stdout.close()
                    proc.stderr.close()
                result = self.fresh({'action': 'call', 'name': 'word_count', 'input': {'text': 'a b'}})
                self.assertTrue(result['ok'], result)
                expected = ['A', 'B'] if point == 'published' else ['a', 'b']
                self.assertEqual(result['value']['words'], expected)

    def test_validation_and_calls_use_injected_executor(self):
        calls = []
        def executor(path, value):
            calls.append((Path(path).read_text(), value))
            return {'result': value}
        store = module.ToolStore(self.root, executor)
        source = '# executor controls execution in this fixture'
        digest = store.promote('delegated', source, [
            {'input': 1, 'expected': {'result': 1}},
            {'input': 2, 'expected': {'result': 2}},
        ])
        self.assertEqual(store.call('delegated', 3), {'result': 3})
        self.assertEqual(calls, [(source, 1), (source, 2), (source, 3)])
        self.assertEqual(digest, hashlib.sha256(source.encode()).hexdigest())

    def test_same_version_can_be_promoted_again(self):
        digest = self.seed()
        self.assertEqual(self.store.promote('word_count', V1, CASE1), digest)
        self.assertEqual(self.store.list_tools(), {'word_count': digest})
        self.assert_v1()

    def test_provided_executor_bounds_protocol_and_lifetime(self):
        # This also catches fixture/environment mistakes independently of a submission.
        for source, text in [('while True: pass', 'timeout'),
                             ('print("x" * 100000)', 'output limit'),
                             ('print("undefined")', 'JSON')]:
            path = Path(self.temp.name) / 'runtime.py'
            path.write_text(source)
            started = time.monotonic()
            with self.assertRaisesRegex(ToolError, text):
                execute(path, {})
            self.assertLess(time.monotonic() - started, 4)


if __name__ == '__main__':
    unittest.main(verbosity=2)

"""Persistent registry of example-validated, content-addressed Python tools."""
import hashlib
import json
import math
from pathlib import Path
import re
import uuid

from tool_runtime import ToolError, atomic_write, execute, fault


_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,47}', re.ASCII)
_VERSION = re.compile(r'[0-9a-f]{64}', re.ASCII)


def _name(name):
    if not isinstance(name, str) or _NAME.fullmatch(name) is None:
        raise ToolError('invalid tool name')


def _json_value(value):
    """Check JSON's types, including finite numbers and string object keys."""
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json_value(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json_value(item)
        return
    raise ToolError('value must be JSON without NaN or Infinity')


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ToolError('duplicate manifest name')
        result[key] = value
    return result


class ToolStore:
    def __init__(self, root, executor=execute):
        try:
            self.root = Path(root).resolve()
            self.root.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError, TypeError) as error:
            raise ToolError('cannot open registry') from error
        self.executor = executor
        self._load()

    def _artifact(self, version):
        path = self.root / 'blobs' / (version + '.py')
        try:
            data = path.read_bytes()
        except OSError as error:
            raise ToolError('cannot read artifact ' + version) from error
        if hashlib.sha256(data).hexdigest() != version:
            raise ToolError('artifact hash mismatch: ' + version)
        return path

    def _load(self):
        try:
            data = (self.root / 'active.json').read_bytes()
        except FileNotFoundError:
            return {}
        except OSError as error:
            raise ToolError('cannot read manifest') from error
        try:
            active = json.loads(data, object_pairs_hook=_object)
        except (ValueError, UnicodeError, RecursionError) as error:
            raise ToolError('invalid manifest JSON') from error
        if type(active) is not dict:
            raise ToolError('manifest must be an object')
        for name, version in active.items():
            _name(name)
            if not isinstance(version, str) or _VERSION.fullmatch(version) is None:
                raise ToolError('invalid manifest version')
            self._artifact(version)
        return active

    def _write(self, path, data):
        try:
            atomic_write(path, data)
        except OSError as error:
            raise ToolError('cannot save registry file') from error

    def _invoke(self, path, value):
        try:
            result = self.executor(path, value)
            _json_value(result)
            return result
        except ToolError:
            raise
        except Exception as error:
            raise ToolError('tool execution failed: ' + str(error)) from error

    def list_tools(self):
        return self._load()

    def call(self, name, value):
        _name(name)
        active = self._load()
        if name not in active:
            raise ToolError('unknown tool: ' + name)
        return self._invoke(self._artifact(active[name]), value)

    def promote(self, name, source, cases):
        _name(name)
        if not isinstance(source, str) or not source:
            raise ToolError('source must be non-empty text')
        try:
            data = source.encode('utf-8')
        except UnicodeError as error:
            raise ToolError('source must encode as UTF-8') from error
        if len(data) > 65536:
            raise ToolError('source limit exceeded')
        if not isinstance(cases, list) or not 1 <= len(cases) <= 32:
            raise ToolError('validation requires 1–32 cases')
        try:
            for case in cases:
                if type(case) is not dict or set(case) != {'input', 'expected'}:
                    raise ToolError('each case requires exactly input and expected')
                _json_value(case['input'])
                _json_value(case['expected'])
            # Own a snapshot so executor mutations cannot alter the expectations.
            cases = json.loads(json.dumps(cases, allow_nan=False))
        except (ValueError, TypeError, RecursionError) as error:
            raise ToolError('invalid validation JSON') from error

        active = self._load()
        version = hashlib.sha256(data).hexdigest()
        staged = self.root / 'staging' / (uuid.uuid4().hex + '.py')
        self._write(staged, data)
        fault('staged')
        for case in cases:
            result = self._invoke(staged, case['input'])
            if result != case['expected']:
                raise ToolError('validation result did not match expected value')
        fault('validated')

        artifact = self.root / 'blobs' / (version + '.py')
        # Existing content-addressed files must never be replaced, even if corrupt.
        if artifact.exists():
            self._artifact(version)
        else:
            self._write(artifact, data)
        active[name] = version
        manifest = json.dumps(active, sort_keys=True, allow_nan=False).encode('utf-8')
        fault('before-publish')
        self._write(self.root / 'active.json', manifest)
        fault('published')
        return version

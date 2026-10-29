"""Durable validated tool registry. Single publisher, process-crash contract."""
import hashlib
import json
from pathlib import Path
import re
from tool_runtime import MAX_BYTES, ToolError, atomic_write, execute, fault

NAME = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,47}', re.ASCII)
DIGEST = re.compile(r'[0-9a-f]{64}', re.ASCII)


def valid_name(name):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ToolError('invalid tool name')


class ToolStore:
    def __init__(self, root, executor=execute):
        self.root = Path(root)
        self.executor = executor
        self.blobs = self.root / 'blobs'
        self.blobs.mkdir(parents=True, exist_ok=True)
        self.manifest = self.root / 'active.json'

    def _manifest(self):
        if not self.manifest.exists():
            return {}
        try:
            active = json.loads(self.manifest.read_text())
            if not isinstance(active, dict):
                raise ValueError()
            for name, digest in active.items():
                valid_name(name)
                if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
                    raise ValueError()
                source = (self.blobs / (digest + '.py')).read_bytes()
                if hashlib.sha256(source).hexdigest() != digest:
                    raise ValueError()
            return active
        except (ValueError, OSError, ToolError) as error:
            raise ToolError('corrupt tool manifest or artifact') from error

    def list_tools(self):
        return self._manifest()

    def call(self, name, value):
        valid_name(name)
        digest = self._manifest().get(name)
        if digest is None:
            raise ToolError('unknown tool')
        return self.executor(self.blobs / (digest + '.py'), value)

    def promote(self, name, source, cases):
        valid_name(name)
        if not isinstance(source, str):
            raise ToolError('source must be text')
        data = source.encode('utf-8')
        if not data or len(data) > MAX_BYTES:
            raise ToolError('source size limit')
        if not isinstance(cases, list) or not 1 <= len(cases) <= 32:
            raise ToolError('one to 32 validation cases required')
        try:
            for case in cases:
                if not isinstance(case, dict) or set(case) != {'input', 'expected'}:
                    raise ValueError()
                json.dumps(case, allow_nan=False)
        except (ValueError, TypeError) as error:
            raise ToolError('invalid validation cases') from error
        active = self._manifest()
        digest = hashlib.sha256(data).hexdigest()
        path = self.blobs / (digest + '.py')
        atomic_write(path, data)
        fault('staged')
        for case in cases:
            if self.executor(path, case['input']) != case['expected']:
                raise ToolError('validation result mismatch')
        fault('validated')
        active[name] = digest
        fault('before-publish')
        atomic_write(self.manifest, json.dumps(active, sort_keys=True).encode())
        fault('published')
        return digest

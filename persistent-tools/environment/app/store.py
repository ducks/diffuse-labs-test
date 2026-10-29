"""Prototype: works in one session, but failed updates and restarts lose tools.

Repair this file. See instruction.md and the provided tool_runtime primitives.
"""
from pathlib import Path
from tool_runtime import atomic_write, execute, fault


class ToolStore:
    def __init__(self, root, executor=execute):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.executor = executor
        self.active = {}

    def list_tools(self):
        return dict(self.active)

    def call(self, name, value):
        return self.executor(self.root / (name + '.py'), value)

    def promote(self, name, source, cases):
        path = self.root / (name + '.py')
        atomic_write(path, source.encode())
        fault('staged')
        self.active[name] = name
        for case in cases:
            self.executor(path, case['input'])
        fault('validated')
        fault('before-publish')
        fault('published')
        return name

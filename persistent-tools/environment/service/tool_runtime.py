"""Provided execution/storage primitives. Not an editable part of the task."""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time

MAX_BYTES = 65536


class ToolError(Exception):
    pass


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def fault(point):
    """Public deterministic interruption seam, inert outside fault-injection runs."""
    if os.environ.get('TOOLSTORE_FAULT') == point:
        print('BARRIER:' + point, flush=True)
        sys.stdin.readline()


def execute(path, value):
    """Run JSON-in/JSON-out Python; bound time, input, output, and child lifetime.

    This is process containment for fixtures, not a hostile-code sandbox.
    All subprocess descendants must stay in the created process group.
    """
    try:
        payload = json.dumps(value, allow_nan=False).encode() + b'\n'
    except (ValueError, TypeError) as error:
        raise ToolError('input must be JSON') from error
    if len(payload) > MAX_BYTES:
        raise ToolError('input limit exceeded')
    with tempfile.TemporaryDirectory() as cwd, tempfile.TemporaryFile() as incoming:
        incoming.write(payload)
        incoming.seek(0)
        proc = subprocess.Popen(
            [sys.executable, '-I', str(Path(path).resolve())],
            stdin=incoming, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            cwd=cwd, env={'PATH': os.defpath}, start_new_session=True,
        )
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        output = bytearray()
        deadline = time.monotonic() + 0.75
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ToolError('execution timeout')
                for key, _ in selector.select(remaining):
                    block = os.read(key.fileobj.fileno(), 8192)
                    if not block:
                        selector.unregister(key.fileobj)
                    else:
                        output.extend(block)
                        if len(output) > MAX_BYTES:
                            raise ToolError('output limit exceeded')
            try:
                status = proc.wait(timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as error:
                raise ToolError('execution timeout') from error
            if status:
                raise ToolError('tool exited unsuccessfully')
            try:
                return json.loads(output, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            except (ValueError, UnicodeError) as error:
                raise ToolError('tool must return one JSON value') from error
        finally:
            selector.close()
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            proc.stdout.close()

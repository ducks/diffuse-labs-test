# Retain validated tools across agent sessions

Our agent can generate small Python tools, but its registry forgets them on
restart, accepts broken candidates, and overwrites working tools before a
replacement is ready. Repair `/app/store.py` so a capability acquired in one
session can safely be reused in a later session with no conversation history.

The generated candidates and validation examples are supplied by callers. This
is a registry repair task: no LLM, model credentials, external network, or tool
generation service is required. Only `store.py` is editable. The supplied
`/opt/task-service/tool_runtime.py` is readable but not part of your submission.

## Public interface

Keep `ToolStore(root, executor=execute)` with these methods:

- `promote(name, source, cases)` validates and saves a candidate, returning its
  version ID: SHA-256 hex of the exact UTF-8 source bytes. `source` is Python
  program text, not a path. Each invocation reads one JSON value from stdin
  and writes exactly one JSON value to stdout. Candidates may fail or hang.
- `list_tools()` returns a fresh dictionary mapping active names to version IDs.
- `call(name, value)` invokes the saved active version through the injected
  `executor(path, value)` and returns its JSON result. An unknown name fails.

Names must match ASCII `[A-Za-z][A-Za-z0-9_-]{0,47}`. Reject invalid names before
writing anything derived from them. Source must be non-empty text whose UTF-8
encoding is at most 65,536 bytes. Cases must be a list of 1–32 dictionaries,
each containing exactly `input` and `expected`, both JSON values without NaN or
Infinity. Every case must execute successfully and equal its expected value.
Do not accept an empty validation set. Errors must raise the provided `ToolError`
(or a subclass); never claim a failed invocation or promotion succeeded.

Persist immutable source artifacts at `root/blobs/<version>.py`. Publish active
versions through `root/active.json`, a JSON object mapping names to 64-character
lowercase SHA-256 version IDs. A missing manifest means an empty registry.
Invalid manifest data, missing artifacts, and artifact/hash mismatches must
raise `ToolError`; do not silently reset, repair, or overwrite corrupt state.
These filenames are an interchange contract, not an implementation suggestion.

## Required behavior

- Validate the full candidate before publishing it. A failed new tool must not
  appear in discovery. A failed replacement must preserve its previous active
  version and actual behavior, as well as every unrelated tool.
- A separate fresh Python process must discover and invoke saved tools. Do not
  depend on an earlier session's memory, candidate files, or current directory.
- Always invoke tools through the supplied executor, including validation and
  ordinary calls. It enforces JSON, time, output, and process-group limits. Do
  not execute candidate code inside the harness with `exec` or import it.
- Keep active artifacts immutable. Orphan staged files are acceptable. Use the
  provided `atomic_write(path, bytes)` for durable atomic file replacement.
- Preserve the old working manifest until the complete new version is ready.
  After interruption at the required seams, a fresh process must see a complete
  working registry. Prior to publication the old version must remain active;
  after publication the new version must be active.
- Preserve all existing names when a later process promotes an additional tool.
- Propagate execution errors clearly. A tool that passed examples may still
  fail on a later input; do not substitute cached example results or mark it
  successful. Passing examples is not proof of general semantic correctness.

## Interruption seams

Call provided `fault(point)` at each seam, exactly once per valid promotion:

1. `staged`: candidate source saved privately, before running validation.
2. `validated`: all validation cases passed; active manifest unchanged.
3. `before-publish`: new artifacts durable, immediately before manifest update.
4. `published`: complete active manifest durably replaced, before returning.

These calls are inert normally. In fault-injection runs the matching seam emits
`BARRIER:<point>` and waits for stdin so the test driver can kill the process
without relying on timing. Do not catch, disable, or move these boundaries to
misrepresent publication order. Failed validation cannot reach `validated`.

One publisher at a time is sufficient. This task covers process death at those
four seams, not arbitrary power loss, concurrent publishers, or hostile file
mutation during execution. Artifact corruption between invocations must still
be detected. The provided executor bounds cooperative process groups but is
not a sandbox for malicious Python escaping its group. All fixtures run in a
disposable Linux container; no credentials or external access are needed.

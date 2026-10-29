# Persistent capability acquisition

Status: implemented and functionally validated. See `instruction.md` for the
final contract and `QUALITY.md` for controls and Harbor results. The original
design below explains the scope; agent difficulty still needs pilot runs.

## Proposed task

Repair a small agent harness that accepts candidate Python tools, validates
them, promotes working versions, and makes them available to later processes.
A scripted agent supplies generated tool candidates; no live model calls are
needed. The coding agent repairs the harness, rather than being graded on a
model's ability to invent a useful tool.

The demonstration is concrete: session A creates and validates a tool; session B
starts with no conversation history and discovers and successfully invokes it.
A broken replacement must leave the previous working version usable, including
after a process crash during promotion.

## Scope and public contract

Use Python standard library tooling inside a disposable container. Candidates
implement a documented JSON stdin/stdout protocol. MCP integration is optional
future work; this task assesses the registry and promotion boundary.

Expose an importable `ToolStore(root, executor)` with these operations:

- `promote(name, source, cases)`: validate names and bounded source size; stage
  an immutable candidate; execute it against supplied input/output examples;
  atomically publish the new version only after every validation case succeeds.
- `list_tools()`: enumerate active names and content version IDs from durable
  state. A new instance must not depend on earlier Python objects or history.
- `call(name, input)`: resolve the active immutable artifact and execute it
  through the supplied bounded executor. Surface execution errors explicitly.

The executor is provided, readable, and outside editable submission files. It
runs each invocation in a subprocess with time and output limits, validates the
JSON protocol, and terminates timed-out process groups. It is not a security
sandbox for arbitrary hostile Python. The container is the disposable trust
boundary; no credentials or external networking are required.

Candidates in the fixtures perform deterministic text and structured-data
transformations. The verifier independently checks behavior on additional
inputs after promotion. Those inputs test that the harness retained and
executes the actual artifact; they are not an undisclosed validation gate that
the harness was expected to infer.

A candidate passing supplied cases can still be semantically wrong. The task
claims reliable validation and publication mechanics, not general proof that a
generated tool is correct or useful.

## Durable publication model

Use content-addressed immutable artifacts and a single atomically replaced
active manifest. Give the starting code an atomic-write/fsync helper, as in the
session-recovery task. Focus repairs on ordering, validation, name resolution,
and durable versus in-memory state rather than reinventing storage primitives.

One writer at a time; no concurrent publication contract. Existing calls may
finish against the version they resolved. Concurrent calls and arbitrary host
power loss are outside the initial task. Process death at explicit handshake
boundaries is in scope. Leftover unreferenced staged artifacts are harmless.

## Behavioral verifier plan

1. Promote a correct tool and invoke it on independent inputs.
2. Start a separate process with an empty session; list and invoke that tool.
3. Reject syntax errors, wrong expected results, malformed protocol responses,
   runtime exceptions, timeouts, and excess output. Keep the prior active tool.
4. Exercise two tool names and multiple versions, including replacing one tool
   without changing the other. Do not hardcode fixture names or source text.
5. Kill the harness at explicit barriers after staging, after validation, and
   immediately before/after manifest publication. A fresh process must see a
   complete old or complete new working version, never an invalid manifest or
   partially written source. A replacement whose validation failed cannot win.
6. Reject invalid/path-traversing names before writing outside the store.
7. Delete the original candidate file after promotion; calls must use the saved
   immutable artifact, not a transient source path or an in-memory callable.
8. An unknown name and a corrupt manifest must fail clearly, without silently
   claiming successful acquisition or overwriting existing state.

Use bounded stdout/stdin handshakes for fault injection rather than sleeps.
Inspect durable artifacts and actual invocation results independently of CLI
success messages. Keep verifier and oracle out of the agent image.

## Required quality controls

- Reference solution and a structurally different valid solution both pass.
- Untouched starting implementation fails.
- Validate-but-never-save, save-before-validate, in-memory-only, and
  overwrite-working-source-before-validation shortcuts each fail.
- A tool-name-hardcoded implementation fails varied names and transformations.
- Container verifier entry points and real Harbor oracle/nop trials yield the
  expected rewards without infrastructure errors.

Difficulty remains uncalibrated until actual agent pilots. This complements the
session-recovery task through artifact validation and version promotion; avoid
making crash persistence the only interesting repair a second time.

## Implementation order

1. Specify exact errors, JSON protocol, manifest schema, and fault barriers.
2. Build the executor and independent verifier around an oracle implementation.
3. Create the intentionally broken starting harness from realistic mistakes.
4. Add alternative solution and negative controls; validate locally.
5. Package in the pinned Nix/Harbor workflow and run container/Harbor controls.

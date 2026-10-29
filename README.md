# Diffuse Labs take-home

Five tasks are requested for the assignment. This repository currently contains
**three implemented tasks**: interrupted agent-session recovery, streaming
inference failover, and persistent capability acquisition.
No claim is made yet that the full assignment is complete.

| Task | Capability assessed | Failure modes | Success checks | Quality controls |
| --- | --- | --- | --- | --- |
| `session-recovery` | Recover durable agent state across process crashes and external effects | Duplicate actions; lost tool-call IDs/history; unpaired results; cross-session key reuse; repeated completion messages | Independent SQLite receipts, exact transcript pairing, nine deterministic crash cases, repeated crashes, completed-session replay, corrupt state, session identity, empty plans | Canonical solution and alternative idempotent-replay solution must pass; original code and two shortcuts must fail |
| `streaming-gateway` | Safe provider failover and async resource ownership | Mixed-provider output, hidden partial failures, capacity leaks, buffering, oversubscription | 16 tests covering stream boundaries, cancellation, concurrent requests, payload/byte integrity, and real localhost HTTP | Canonical and priming-based solutions pass; original code plus four incorrect fixes fail |
| `persistent-tools` | Validate and retain generated tools across sessions | Premature promotion, forgotten state, overwritten working tools, invalid artifacts, crashes during publication | 17 tests covering separate processes, independent tool versions, validation failures, corruption, injected executors, bounds, and four deterministic crash seams | Canonical and alternative private-staging solutions pass; original code plus six incorrect fixes fail |

## Local development

```sh
nix-shell
python scripts/validate.py
python scripts/validate_gateway.py
python scripts/validate_tools.py
```

Or run `nix-shell --run 'python scripts/validate.py'`.
`shell.nix` pins Nixpkgs by revision and content hash. It supplies Python, Git,
uv, and Docker tooling. The task and local verifier need only the Python standard
library. No pipx installation or model credentials are used.
First entry may need network access to obtain the pinned Nix dependencies.

The validation script runs every control against the same behavioral verifier
and writes logs plus `logs/validation.json` (gitignored). It does not replace the
broken starting code. All fixtures and databases are disposable temp files.

## Task layout

```
session-recovery/
  task.toml
  instruction.md
  environment/
    Dockerfile
    app/runner.py              # intentionally broken starting point
    app/plan.json
    service/tool_service.py    # external API stand-in; not editable in the task
  tests/test.sh                # Harbor verifier entry point
  tests/verify.py
  solution/solve.sh            # Harbor oracle entry point
  solution/runner.py
```

The Dockerfile copies only `environment/app` and `environment/service` into the
agent environment. Tests and solution stay outside the agent workspace and are
mounted by Harbor for verification/oracle execution. The service is readable
for its public API contract but changes to it are not part of a submission.

## Container and Harbor execution

Enter `nix-shell`, then:

```sh
# Validate real verifier entry points and rewards for all five controls.
python scripts/validate.py --container

# Install the exact Harbor dependencies into this repo's .venv.
uv sync --frozen

# Run real Harbor oracle and untouched-baseline trials and check their rewards.
python scripts/validate_harbor.py

# Streaming gateway: container controls and Harbor trials.
python scripts/validate_gateway.py --container
python scripts/validate_harbor.py --task streaming-gateway

# Persistent tool acquisition: container controls and Harbor trials.
python scripts/validate_tools.py --container
python scripts/validate_harbor.py --task persistent-tools
```

Harbor 0.25.0 and its dependency graph are pinned by `pyproject.toml` and
`uv.lock`. uv uses Nix's Python and will not download another interpreter.
Docker Engine must be running and accessible. The shell supplies matching
Compose/Buildx plugins and a writable, gitignored `.docker` configuration;
it does not change your global Docker settings.

The package uses Harbor's `task.toml`, Docker environment, `/tests/test.sh`,
`/solution/solve.sh`, and `/logs/verifier/reward.txt` conventions. Full Harbor
trials are verified: oracle reward **1.0**, nop reward **0.0**, no trial errors.
All controls for all three tasks produce their expected rewards through the container
verifier entry points. Each task’s `QUALITY.md` records the scope.

Harbor can exit zero even when a trial has an infrastructure error. The
validation script checks completion, error counts, and rewards in the actual
result JSON, rather than trusting the CLI exit code. Results remain local in
`logs/`; nothing is uploaded.

## Evaluation design

The runner represents a real agent's persistence/execution loop, with a
precomputed plan replacing model output. Tasks require no model calls. Tool
results and effects are committed together in a separate SQLite service, which
supports receipt lookup and payload-checked idempotency keys. This makes the
uncertain-outcome window solvable: recovery can query a receipt or repeat the
same idempotent request. A non-idempotent service without receipts would not
permit a general exactly-once guarantee.

Fault injection uses explicit stdout/stdin handshakes. The verifier waits for
the selected boundary, sends SIGKILL, waits for process exit, and resumes.
Deadlines bound hangs; no sleep determines when a crash occurs. It checks the
service's committed ledger independently of the runner's final success claim.

The benchmark covers **process death at the three specified boundaries**,
not machine power loss, concurrent writers to one session, changed plans,
malicious filesystem modification, or arbitrary interruption inside SQLite or
filesystem syscalls. Atomic writes and fsync are provided in the starting code.
The focus is recovery reasoning rather than implementing a storage engine.

The short fixture is a starting difficulty calibration. Before submission,
pilot with actual agent attempts and report observed failure modes and solve
rates. Do not equate negative-control failures with proof the task is hard.

## Streaming gateway design

The second task is the async streaming core behind an inference HTTP gateway.
It uses a public transport interface with scripted deterministic faults and a
working localhost HTTP adapter. Byte delivery is the commit point: fallback is
safe before the first non-empty chunk, but would corrupt the response afterward.
Admission and cleanup are tested across overlapping requests on one event loop.

The two valid control implementations use different strategies: track a commit
flag while relaying, or prime the stream before leaving the retryable section.
The latter confirms that grading does not depend on the reference code structure.
The HTTP adapter is deliberately narrow (HTTP/1.0, no TLS or chunked transfer);
this task tests the gateway core, not general HTTP compliance or a real model.

## Persistent tool acquisition design

The third task repairs a registry for tools generated by an agent. Candidates
are deterministic JSON-in/JSON-out Python programs. A provided executor bounds
time, input, output, and process-group lifetime; no model calls are needed.
The repaired harness must validate every supplied example before publishing an
immutable source version through a durable manifest. Later processes discover
and invoke the actual saved source without prior conversation history.

The verifier exercises failed replacements, independent tools, corrupt state,
fresh processes, injected execution, and SIGKILL at four explicit publication
seams. Reference and private-staging alternatives both pass. The task addresses
validation and durable capability retention, not model training or proof that
a tool passing a few examples is universally correct. Candidate execution is
not a sandbox for hostile Python. See `persistent-tools/instruction.md`,
`persistent-tools/DESIGN.md`, and `persistent-tools/QUALITY.md` for the contract,
limits, and validation evidence.

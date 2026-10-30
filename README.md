# Diffuse Labs take-home

Five tasks are requested for the assignment. Three implemented tasks are
currently selected: interrupted agent-session recovery, streaming inference
failover, and dataset-worker incident containment. The assignment is incomplete.

The earlier `persistent-tools` prototype and its successful model pilot are
retained for reference, but are set aside from the selected task set.

| Task | Capability assessed | Failure modes | Success checks | Quality controls |
| --- | --- | --- | --- | --- |
| `session-recovery` | Recover durable agent state across crashes and external effects | Duplicate actions, lost calls/history, cross-session reuse | Independent receipts, transcript pairing, explicit crash boundaries | Canonical and alternate solutions; baseline and incorrect fixes |
| `streaming-gateway` | Safe provider failover and async resource ownership | Mixed-provider output, capacity leaks, buffering, oversubscription | 16 tests including real localhost HTTP | Two valid solutions; baseline and four incorrect fixes |
| `dataset-containment` | Contain a credential/file-boundary incident while retaining service and output correctness | Refresh-based access, recurring exports, duplicate outputs, lost backlog, collateral outages | Live HTTP traffic, independent ledgers and publication provenance, lost acknowledgements, actual worker restarts | Canonical and code-level loader-policy repairs; baseline and eight partial/incorrect repairs |

## Local development

```sh
nix-shell
python scripts/validate.py
python scripts/validate_gateway.py
python scripts/validate_containment.py
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

# Dataset incident containment: container controls and Harbor trials.
python scripts/validate_containment.py --container
python scripts/validate_harbor.py --task dataset-containment
```

Harbor 0.25.0 and its dependency graph are pinned by `pyproject.toml` and
`uv.lock`. uv uses Nix's Python and will not download another interpreter.
Docker Engine must be running and accessible. The shell supplies matching
Compose/Buildx plugins and a writable, gitignored `.docker` configuration;
it does not change your global Docker settings.

The package uses Harbor's `task.toml`, Docker environment, `/tests/test.sh`,
`/solution/solve.sh`, and `/logs/verifier/reward.txt` conventions. Full Harbor
trials are verified: oracle reward **1.0**, nop reward **0.0**, no trial errors.
Each implemented task has its own control and Harbor validation record. Each task’s `QUALITY.md` records the scope.

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

## Dataset incident containment

This task adapts the v4 dataset-worker incident on Replaybook Infra's
`feature/dataset-worker-containment` branch, pinned at `f8e2936`.
The agent patches worker code and writes a reusable deployment repair procedure.
During grading, real HTTP services keep handling client reads and preview jobs
while that procedure closes the file boundary, revokes compromised capabilities,
removes unauthorized persistence, and recovers previously published outputs.

Verification checks actual retained state, fresh work, publication provenance,
continued legitimate reporting and client access, acknowledgement failures, and
recovery after worker-process restarts and recreated core HTTP servers. It does not claim the original NixOS
scenario's full host-reboot or VM-isolation guarantees. Source provenance and
all adaptation limits are in `dataset-containment/PROVENANCE.md`.

## Set-aside tool-storage prototype

`persistent-tools` and `scripts/validate_tools.py` remain available as an
exploratory prototype. Its first independent Codex pilot passed all tests in
about 56 seconds. See `pilots/persistent-tools-codex-001/README.md`. Its original
hard-difficulty estimate is not established, and it is currently excluded from
the selected assignment tasks.

The first independent `dataset-containment` Codex pilot also passed, in about
84 seconds at low reasoning effort. See
`pilots/dataset-containment-codex-001/README.md`. This port has not established
hard difficulty; its results are separate from the original NixOS scenario.

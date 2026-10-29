# Diffuse Labs take-home

Five tasks are requested for the assignment. This repository currently contains
**one implemented task**, starting with interrupted agent-session recovery.
No claim is made yet that the full assignment is complete.

| Task | Capability assessed | Failure modes | Success checks | Quality controls |
| --- | --- | --- | --- | --- |
| `session-recovery` | Recover durable agent state across process crashes and external effects | Duplicate actions; lost tool-call IDs/history; unpaired results; cross-session key reuse; repeated completion messages | Independent SQLite receipts, exact transcript pairing, nine deterministic crash cases, repeated crashes, completed-session replay, corrupt state, session identity, empty plans | Canonical solution and alternative idempotent-replay solution must pass; original code and two shortcuts must fail |

## Local development

```sh
nix-shell
python scripts/validate.py
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
```

Harbor 0.25.0 and its dependency graph are pinned by `pyproject.toml` and
`uv.lock`. uv uses Nix's Python and will not download another interpreter.
Docker Engine must be running and accessible. The shell supplies matching
Compose/Buildx plugins and a writable, gitignored `.docker` configuration;
it does not change your global Docker settings.

The package uses Harbor's `task.toml`, Docker environment, `/tests/test.sh`,
`/solution/solve.sh`, and `/logs/verifier/reward.txt` conventions. Full Harbor
trials are verified: oracle reward **1.0**, nop reward **0.0**, no trial errors.
All five controls also produce their expected rewards through the container
verifier entry point. See `session-recovery/QUALITY.md` for the scope of checks.

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

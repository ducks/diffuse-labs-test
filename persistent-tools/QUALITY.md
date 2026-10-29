# Quality-control record

Validated 2026-10-29 in the pinned Nix shell, digest-pinned Docker environment,
and repo-local Harbor 0.25.0. This is the third implemented assignment task.

## Commands

```sh
nix-shell --pure --run 'python scripts/validate_tools.py'
nix-shell --run 'python scripts/validate_tools.py --container'
nix-shell --run 'python scripts/validate_harbor.py --task persistent-tools'
```

## Results

| Control | Local | Container reward |
| --- | --- | --- |
| Canonical content-addressed staging | Pass | 1 |
| Alternative private staging, install after validation | Pass | 1 |
| Original code / no-op | Fail | 0 |
| Validate but never publish | Fail | 0 |
| Skip behavioral validation | Fail | 0 |
| Publish before validation | Fail | 0 |
| Retain active state only in memory | Fail | 0 |
| Overwrite existing active source | Fail | 0 |
| Support only a hardcoded tool name | Fail | 0 |

Real Harbor oracle: **1 completed trial, 0 errors, reward 1.0**.
Real Harbor nop: **1 completed trial, 0 errors, reward 0.0**.
The validation script inspects actual result JSON, not only the CLI exit code.

All controls run the same 17 behavioral test methods, on Python 3.14.7 locally
and Python 3.12.8 in the container. The test set includes multiple cases within
individual methods. No model APIs or third-party runtime libraries are needed.

## What is tested

Fresh-process discovery and invocation; new processes preserving prior names;
multiple tool names and independent versions; source-derived version IDs;
all validation cases being checked; syntax/runtime errors; wrong results;
malformed/multiple JSON outputs; time and output bounds; empty and oversized
validation sets and source; input bounds; invalid/path-traversing names;
unknown tools; corrupt manifests and missing/tampered artifacts; injected
executors; repeated promotion; and deleting the original generated source file.

Four crash cases stop a replacement at explicit stdout/stdin barriers after
staging, after validation, before publication, and after publication. The
verifier sends SIGKILL, waits for exit, then starts a separate process to invoke
the saved tool. The old version must work before publication; the new version
must work afterward. No sleep determines where a crash occurs. Timeouts only
bound hangs and subprocess execution.

The alternative solution validates a candidate in a private temporary directory
before installing its content-addressed artifact. The canonical solution stages
the immutable content artifact before validation. Both use the documented
manifest/artifact interchange format and the supplied durable-write primitive.

## Limits and calibration

The task tests acquisition infrastructure with scripted candidate generation;
it does not test whether a model invents useful tools or gets better over time.
Passing supplied examples is not proof of general tool correctness. Independent
post-promotion inputs check actual artifact reuse, not an undisclosed gate that
the harness should somehow infer during validation.

The durable-storage contract is single-publisher and covers process death at
specified boundaries. It does not cover arbitrary host power loss, concurrent
publication, malicious filesystem races, or tamper-proof manifests. Artifacts
are checked for consistency with the manifest, not authenticity.

The executor kills a tool's process group and bounds output in memory. It does
not contain hostile code that escapes its process group or accesses the host
filesystem. Candidates are trusted deterministic fixtures in a disposable Linux
container; MCP transport and automatic owner approval are outside this task.
The public runtime is readable but changes to it are disallowed. Tests and
solutions are not copied into the agent environment.

Functional controls establish validity, not solve difficulty. The `hard`
metadata is provisional until coding-agent pilots report actual solve rates
and failure modes. Two more tasks are still needed for the five-task assignment.

Detailed control logs and result summaries are gitignored under
`logs/persistent-tools/`; Harbor trials are under `logs/harbor/`. Nothing is
uploaded by these scripts.

# Diffuse Labs MTS take-home

Five self-contained Harbor 0.25.0 task packages. Each contains a broken starting
application, an explicit behavioral contract, a reference repair and protected
executable verification. No model/API account or cloud infrastructure is needed
to run the controls and graders. Model difficulty is not established by these
controls; earlier pilots are retained under `pilots/`.

| Task | Capability assessed | Failure modes observed | How success is checked | Quality controls |
| --- | --- | --- | --- | --- |
| `session-recovery` | Recover durable agent sessions after process crashes | Lost pending calls, repeated external actions, discarded history | Explicit crash handshakes, independent SQLite receipts, transcript pairing, repeated recovery and separate sessions | Canonical and idempotent-replay alternate; no-op, skip-pending and reset-plan controls |
| `streaming-gateway` | Fail over providers while preserving streams and capacity | Mixed-provider output, missing fallback, resource leaks, whole-stream buffering; premature verifier exit | Async concurrency/cancellation tests and real localhost HTTP; trusted parent requires complete suite execution | Canonical and stream-priming alternate; six negative controls including exit-zero exploit |
| `dataset-containment` | Contain credential/file-boundary abuse without losing legitimate work | Continuing exports, refresh access, duplicated or missing publications, collateral outages | Live HTTP traffic, external receipts/provenance, historical evidence, lost acknowledgements and actual worker restarts | Canonical and code-level policy alternate; no-op and eight partial/incorrect repairs |
| `terraform-k8s` | Deploy and recover a durable service stack | Lost accepted work, volatile database, cold-boot permissions, crossed namespace state, incomplete teardown | Fresh offline K3s VM; six phases including acknowledged worker loss, pod replacement, reboot, no-drift plan, isolation and destroy | Canonical and init-container alternate; no-op, volatile PostgreSQL and reboot-permissions controls |
| `evaluation-integrity` | Repair trustworthy benchmark accounting | Cohort leakage, model/harness misattribution, duplicate retries, mutable benchmark definitions | Protected unseen datasets; explicit interrupted/unavailable rules; retained history; deterministic incremental imports; atomic rejection | Dictionary and SQLite aggregation; isolation probe; no-op, dropped failures, merged cohorts, hardcoded sample, mutable identities, invalid fields, device-symlink outputs, early exit and forged reward controls |

## Reproduce

Requires Linux, a running accessible Docker Engine, Nix and `/dev/kvm`.
Terraform uses a local single-node K3s VM inside its Docker task. Allow at least
8 GiB available RAM and space for the local Nix store/images/VM disks. Downloads
of pinned public dependencies may be needed initially. There is no cloud cluster
or hosted evaluator. Run one Terraform validation at a time. Native Nix builds also need adequate
space in the daemon build directory; RAM-backed temporary storage can be too small.
A per-run `build-dir` override requires a trusted Nix user. Harbor uses its own
container filesystem/store, avoiding that host temporary-storage dependency.

```sh
nix-shell --run 'uv sync --frozen'
# All controls plus oracle/nop Harbor trials, twice from fresh environments:
nix-shell --run 'python scripts/validate_submission.py --rounds 2'
```

The full check is deliberately slow because it boots real clusters. To split it:

```sh
nix-shell --run 'python scripts/validate_submission.py --phase controls --rounds 2'
nix-shell --run 'python scripts/validate_submission.py --phase harbor --rounds 2'
```

For a focused fifth-task check:

```sh
nix-shell --run 'python scripts/validate_integrity.py --container --repeat 2'
nix-shell --run 'python scripts/validate_harbor.py --task evaluation-integrity'
```

Task-specific controls remain available: `scripts/validate.py`,
`validate_gateway.py`, and `validate_containment.py` accept `--container`;
`validate_terraform.py` boots fresh native VMs. Terraform Harbor image preparation
is reproducible via `scripts/prepare_terraform_harbor.py`; the full Harbor phase
runs it automatically. See [the Terraform package guide](terraform-k8s/HARBOR.md).

## Verification and evidence

Every validation invocation retains logs, control results or actual Harbor reward
artifacts under gitignored `logs/`. The suite rejects unexpected rewards and
infrastructure errors even when Harbor exits zero. Evaluated incorrect solutions
must receive 0; canonical solutions must receive 1. Missing KVM, VM/build failures
without an evaluated result, and verifier crashes are not successful checks.

[VALIDATION.md](VALIDATION.md) records the commands and outcomes actually observed,
including the final source hashes/evidence index. [ADVERSARIAL-REVIEW.md](ADVERSARIAL-REVIEW.md)
records demonstrated weaknesses, corrections and limits. Task-specific `QUALITY.md`
files retain their detailed scope and earlier calibration.

Tests and solutions are excluded from agent images; Harbor stages them only for
verification/oracle execution. Terraform and evaluation-integrity use separate
verifier environments. The integrity grader additionally runs submitted code as
an unprivileged subprocess that cannot read its protected tests or modify reward
files. The older shared-environment Python tasks test operational correctness;
they are not full sandboxes against arbitrary hostile Python during grading.

The README→NixOS, Hyprland and persistent-tools prototypes remain available for
research but are excluded from these five selected tasks. No performance or
hard-difficulty claim follows from passing reference/negative controls.

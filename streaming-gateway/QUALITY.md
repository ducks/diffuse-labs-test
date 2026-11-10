# Quality-control record

Validated 2026-10-29 through the pinned Nix shell, Docker verifier entry point,
and repo-local Harbor 0.25.0.

## Commands

```sh
nix-shell --pure --run 'python scripts/validate_gateway.py'
nix-shell --run 'python scripts/validate_gateway.py --container'
nix-shell --run 'python scripts/validate_harbor.py --task streaming-gateway'
```

## Results

| Control | Local | Container reward |
| --- | --- | --- |
| Canonical commit-flag implementation | Pass | 1 |
| Alternative stream-priming implementation | Pass | 1 |
| Original code / no-op | Fail | 0 |
| Retry after partial output | Fail | 0 |
| Disable all failover | Fail | 0 |
| Close responses but leak reservation counts | Fail | 0 |
| Buffer the whole response | Fail | 0 |

Real Harbor oracle: **1 completed trial, 0 errors, reward 1.0**.
Real Harbor nop: **1 completed trial, 0 errors, reward 0.0**.

All controls run the same 16 test methods. Local execution uses Python 3.14.7;
the digest-pinned container uses Python 3.12.8. Neither implementation needs
third-party libraries or model credentials.

## What is tested

Provider-open and initial-body failures, post-commit error propagation, prompt
first-byte delivery, arbitrary SSE/UTF-8 fragmentation, unchanged payloads,
successful empty responses, cancellation during open/read, early generator
close, request-local cleanup, reservations during concurrent opens, all-busy
admission, recovery after exhausted providers, unexpected exception propagation,
non-default provider names, and constructor validation.

The localhost HTTP test uses two real TCP servers. One returns HTTP 503; the
other sends headers and the first body chunk, then waits on an explicit event.
The verifier must receive the first chunk before allowing the server to finish.
This catches buffering without comparing elapsed performance measurements.
Deadlines only bound hangs. Concurrent fixture tests also use event handshakes,
not sleeps that guess the order of requests.

## Limits and remaining calibration

The task covers a single asyncio event loop, one cancellation request at a time,
and an idempotent, non-throwing response-close contract. It does not claim to
test multi-process admission, repeated cancellation during cleanup, arbitrary
HTTP protocol compliance, real provider limits, or load-test performance.
Agent correctness is judged at the documented core-library boundary.

Tests and reference solutions are outside the agent's image/workspace. Changes
to the public transport are disallowed, as specified in the task instruction.
Functional controls establish task validity, not model solve difficulty. The
`hard` metadata remains provisional until actual coding-agent pilots are run.

Detailed logs are gitignored under `logs/streaming-gateway/`; full Harbor trials
are under `logs/harbor/`. Nothing is uploaded by the validation scripts.

## Confirmed early-exit verifier defect and correction (2026-11-09)

Adversarial reproduction: a candidate consisting only of `import os; os._exit(0)`
caused the original verifier to exit zero while importing the candidate, before
running any tests. The original shell entry point then published reward 1.
This was reproduced directly against the native verifier (exit 0, no output),
not inferred from a hypothetical attack.

The entry point now calls a trusted parent runner that never imports submitted
code. It requires a successful child exit **and** exactly one structured suite
completion record showing every test ran, without failures, errors or skips.
The expected count is derived from the protected test source, not supplied by
the candidate. The child emits that record only after unittest completes.
The early-exit control now fails; canonical and alternate solutions still pass.

`python3 scripts/validate_gateway.py` executed all eight controls after this
correction: both positive controls passed, and all six negative controls failed,
including the reproduced early-exit exploit. This statement is native validation;
Docker and Harbor outcomes must be taken from their separately recorded runs.

This is a fail-closed completion check, **not** a security sandbox for arbitrary
hostile in-process Python. A candidate that deliberately tampers with unittest,
forges the child-result protocol, or attacks the shared container is outside the
protection established here. Tests and solutions are absent during the agent
turn, but importing a library in the grading subprocess does not make its code
an untrusted-code isolation boundary. Do not describe this fix as proving that
protected grading material is inaccessible to malicious code during grading.

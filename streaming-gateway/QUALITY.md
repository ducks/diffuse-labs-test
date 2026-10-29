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

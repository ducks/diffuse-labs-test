# Selected task pilot round 001

Completed 2026-10-29 America/Los_Angeles (2026-10-30 UTC).
Frozen source commit: `eabc130`.

## Setup

Two fresh attempts per selected task, using Codex CLI 0.164.0 with
`openai/gpt-6.1-sol`, low reasoning effort, disabled web search, and a
600-second execution limit. At most two containers ran concurrently, with
no automatic retries. Tool storage was excluded.

`plan.json` records the settings. Task files were frozen from the source commit
before launch; matching task checksums were verified within each pair of
attempts. Earlier pilots are separate and not added to these counts.

The model received each public task environment and instruction in a fresh
container. It did not receive this conversation, previous submissions, the
reference solution, or the hidden verifier. Observed tool calls did not access
hidden test/solution directories. Grading happened after each attempt.

## Results

| Task | Passed | Agent execution times |
| --- | --- | --- |
| Session recovery | 2 / 2 | 43.02 s, 41.44 s |
| Streaming gateway | 2 / 2 | 50.60 s, 40.11 s |
| Dataset containment | 2 / 2 | 80.19 s, 42.03 s |

**6 / 6 passed, 0 evaluated failures, 0 attempt errors, 0 unavailable trials.**
There were no infrastructure errors. Each attempt earned reward **1.0** by
passing every check in its task's behavioral verifier. No decision-model judge
was used. Claims of success alone were not scored.

Reported model cost totals **$0.297814**, known for all six attempts. This is
Harbor's estimate, not an invoice. Times in the table exclude agent dependency
installation, container setup, verification, and artifact collection. This is
not a general cost or performance comparison across models or harnesses.

## What passing means

Session recovery preserves pending call IDs, pairs calls and results, avoids
duplicate external effects across injected process crashes, keeps sessions
independent, and does not append repeated completion messages. The streaming
gateway preserves response bytes, retries only before output commitment,
reserves capacity correctly, and cleans up connections/capacity across failures,
cancellation, and early close without buffering an entire stream.

Dataset containment closes unauthorized file reads, revokes exposed access and
refresh capabilities including derived access, disables unauthorized exports,
preserves legitimate traffic and evidence, reconciles durable outputs without
duplicating publications, and survives the documented worker restarts and
recreated core HTTP servers. It does not claim the original NixOS scenario's
full host-reboot guarantees.

## Submission review

The retained patches implement the required behavior rather than simply
printing success or matching fixture IDs. Recovery patches preserve pending
calls and query committed receipts. Streaming patches track output commitment,
reserve before awaiting upstream work, and release capacity in cleanup. Incident
patches revoke the affected identity, preserve unrelated clients, close the
input boundary, and reconcile existing receipts before publishing.

The patches demonstrate valid variation: one incident repair issues replacement
access without retaining a refresh capability, while the other issues both.
Both revoke the exposed refresh credential and keep the worker operational;
issuing a new refresh credential is not an additional hidden requirement.

## Interpretation

These versions are consistently solvable by this model at low reasoning effort
within about 40–80 seconds. This round provides little support for calling them
hard under these settings. The task verifiers may still be useful correctness
exercises, but passing functional controls is not evidence of model difficulty.

Two attempts on one model do not establish a population solve rate, cross-model
difficulty, or general reliability. Fresh contexts do not make these attempts
representative of every harness, budget, or model. Tests cover their documented
contracts and cannot prove absence of every possible bug.

The next useful design change would add a substantive diagnosis/integration
problem or reduce prescriptive architecture hints while preserving explicit,
fair success requirements. Do not manufacture difficulty through unspecified
requirements, arbitrary traps, or post-hoc changes to these scores.

## Evidence and reproduction

`results.json` records all six trial outcomes, task checksums, durations, usage,
raw-result hashes, and submission hashes. Each trial directory contains the
unmodified submitted source, its verifier output, and a compact summary.
Credentials and private model reasoning are not included.

Full raw Harbor logs/results remain gitignored under
`logs/pilots/selected-tasks-codex-round-001/`. The frozen task trees and launch
configuration remain under `logs/pilots/round-001/`.

To repeat locally, use the same frozen snapshot and settings with a fresh
`job_name`, then run from the repository's pinned Nix shell:

```sh
CODEX_FORCE_AUTH_JSON=1 nix-shell --run 'uv run --frozen harbor run \
  --config logs/pilots/round-001/job-config.json'
```

The archived config uses the original job name; change it before repeating.
This is a model-backed run using the logged-in account's quota. Task snapshots
can be reconstructed with `git archive eabc130 session-recovery
streaming-gateway dataset-containment`. Keep future task revisions visibly
separate from this cohort.

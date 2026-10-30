# Dataset incident task: first independent model pilot

Run date: 2026-10-29 America/Los_Angeles (2026-10-30 UTC).
Task snapshot: `db6edad`; source Replaybook scenario pinned separately in
`dataset-containment/PROVENANCE.md`.

## Setup and result

One independent Codex CLI 0.164.0 / `openai/gpt-6.1-sol` trial at low reasoning
effort, with web search disabled and a 600-second agent execution limit.
Agent dependency installation was outside that execution budget.

- Reward **1.0**, both end-to-end verifier tests passed.
- **1 completed trial, 0 infrastructure errors**.
- Agent execution: **83.91 seconds**.
- Reported tokens: **113,687 input**, including **101,376 cached**, and
  **3,880 output**.
- Harbor-estimated cost: **$0.0735596**, not an invoice amount.

The agent received the starting worker, repair stub, task instruction, and
public runtime in the Docker task. It did not receive this conversation, the
hidden verifier, or the reference repair. Observed commands did not access the
hidden test or solution directories. The verifier ran after the attempt.

`repair.py` and `service.py` are the unmodified collected submission, not a new
oracle. `result-summary.json` records relevant run metadata. Full logs remain
local and gitignored under `logs/pilots/dataset-containment-codex-pilot-001/`.
No credentials or private model reasoning are included in these retained files.

## Patch review

The repair briefly stops only the worker while revoking worker credentials,
issuing replacements, disabling worker-owned export schedules, and persisting
the input-root policy. It leaves the client-facing services running and then
restarts the worker. The loader also enforces the input-directory boundary in
code, so the repair is not relying solely on an environment setting.

The worker prioritizes recovery jobs, looks up existing publication receipts,
rejects mismatched or multiple receipts, and adopts a matching existing output.
New outputs use a stable job-based idempotency key. Queue acknowledgements
reference those actual receipts. This is a legitimate repair of the specified
contract, not a fixture-specific success message or fabricated database state.

## Interpretation

The task is functionally sound under the current checks, but this first
frontier-model attempt passed quickly at low reasoning effort. Its original
`hard` metadata is **not calibrated by this evidence**. A single passing
attempt does not establish a general solve rate, nor does the original
Replaybook scenario's failed Particle attempt establish this port's difficulty.

Compared with the NixOS incident, the agent here authors a repeatable repair
procedure with access to the public implementation, rather than diagnosing and
changing an already-running guest throughout its turn. That distinction may
make this port substantially easier; it should be evaluated directly before
any difficult-task claim. Do not increase difficulty with unspecified
requirements or arbitrary grading traps.

## Reproduction

Use a fresh job name from the repository root:

```sh
CODEX_FORCE_AUTH_JSON=1 nix-shell --run 'uv run --frozen harbor run \
  --path dataset-containment --agent codex --model openai/gpt-6.1-sol \
  --ak version=0.164.0 --ak reasoning_effort=low \
  --ak disable_web_search=true \
  --agent-timeout-multiplier 0.3333333333 \
  --artifact /app/service.py --artifact /app/repair.py \
  --job-name dataset-containment-codex-pilot-002 --jobs-dir logs/pilots'
```

This launches a model-backed attempt using the existing Codex login/quota.
Keep results separate from Replaybook Infra's NixOS scenario and its pilots.

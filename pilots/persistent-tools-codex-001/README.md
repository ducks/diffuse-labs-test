# First persistent-tools coding-agent pilot

Date: 2026-10-29. Task snapshot: `17a1700`.

## Setup

One independent Harbor trial using Codex CLI 0.164.0,
`openai/gpt-6.1-sol`, low reasoning effort, web search disabled, and a
600-second agent execution limit. Agent setup time is outside that limit.
Authentication used the existing local Codex login via Harbor's auth-file
support; no credentials are included here.

The agent received the task instruction and starting Docker environment. The
verifier and reference solution were not included in its starting environment,
and this conversation was not supplied. The submitted artifact was collected
by Harbor after the attempt. Observed commands read the starting code and public
runtime, replaced `store.py`, and ran self-authored checks. They did not access
the hidden verifier or oracle.

## Outcome

- Reward: **1.0**, all **17 test methods passed**.
- Completed trials: **1**; infrastructure errors: **0**.
- Agent execution: **55.59 seconds**; entire trial: **201.99 seconds**, including
  dependency installation, container setup, verification, and collection.
- Reported tokens: **73,448 input**, including **68,480 cached**, and
  **2,770 output**.
- Harbor-estimated model cost: **$0.044484**. This is the harness estimate,
  not a billing statement.

`submission.py` is the unmodified collected solution. `result-summary.json`
retains the relevant machine-readable metadata. Full local logs are gitignored
at `logs/pilots/persistent-tools-codex-pilot-001/`.

## Review and implications

The submission is a genuine implementation of the public contract, rather than
a fixture-specific shortcut. It validates names/cases, snapshots validation
inputs, stages candidate source separately, validates through the executor,
publishes content-addressed artifacts through an atomic manifest, reloads state
on each operation, and verifies artifact hashes. It also adds defensive checks
for duplicate manifest keys and invalid JSON types.

The agent produced the replacement in one implementation pass and exercised its
own checks, without receiving hidden-verifier feedback. This is evidence that
the current instructions make the task accessible to a capable coding agent.
It does **not** support claiming the task has calibrated hard difficulty.

One successful trial is not a measured population solve rate. The next useful
step is either another independent model attempt or a revision that adds a
substantive integration/diagnosis problem. Do not make it harder merely by
omitting requirements or adding arbitrary traps. Keep this task snapshot and
result intact when comparing a revised version.

## Reproduction

From the repository's pinned Nix shell, use a new job name:

```sh
CODEX_FORCE_AUTH_JSON=1 nix-shell --run 'uv run --frozen harbor run \
  --path persistent-tools --agent codex --model openai/gpt-6.1-sol \
  --ak version=0.164.0 --ak reasoning_effort=low \
  --ak disable_web_search=true \
  --agent-timeout-multiplier 0.3333333333 \
  --artifact /app/store.py --job-name persistent-tools-codex-pilot-002 \
  --jobs-dir logs/pilots'
```

This launches a model-backed attempt and uses the logged-in account's quota.
It does not run the oracle or expose its source to the agent.

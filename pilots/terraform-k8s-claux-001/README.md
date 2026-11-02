# Terraform/Kubernetes: Claux + OpenRouter pilot 001

Two isolated single-attempt pilots ran on 2026-11-01. Each used a fresh Claux
session, the same frozen public inputs and prompt as the Codex pilot, low
reasoning effort, 8,192 output tokens per round, a 900-second wall limit, and a
200-round cap. They ran sequentially, with two CPUs and 8 GiB RAM per container.
Neither received private feedback or a second task attempt. One successful
preflight-only run made no paid model call. No provider retries were observed
in the saved model timing entries; Claux's standard provider retry behavior was
not disabled.

| Model | Agent time | Rounds / tool calls | Private result | Reported cost |
| --- | --- | --- | --- | --- |
| Particle-1 | 900.02 s; timed out | 12 / 16 | Failed fresh deployment | $0.013429266 checkpoint; incomplete |
| Claude Opus 5.5 | 811.61 s; completed | 10 / 9 | Passed first three phases; failed cold boot | $0.726516 |

## What failed

**Particle:** it saved a Terraform JSON deployment, performed schema validation,
and ran its own VM tests. The saved submission gave Redis a writable /tmp but
not PostgreSQL. Private grading failed the first apply, and PostgreSQL reported
that it could not create `/tmp/.s.PGSQL.5432.lock` because permission was denied.
The deployment and migration workloads did not become ready. The round limit
was not reached; most of the wall budget was spent in development tool calls.
The last transcript was a running checkpoint, so its cost is not a verified
final bill. No second attempt was made.

**Opus:** its independent development test exercised normal operation,
authorization, a clean plan and destroy. It explicitly said it had not tested
worker interruption, Redis loss, cold boot or a second namespace. The private
verifier then passed fresh deployment, acknowledged worker loss, and backend
replacement. After a full shutdown and boot, PostgreSQL rejected its remounted
data directory's permissions and API readiness timed out. The submission sets
fs_group but omits a change policy or startup permission correction. This
matches the remount-permissions failure encountered during reference development;
we did not repair the submission or count a hypothetical fix as a pass.
Namespace isolation and destroy were not reached in private grading.

## Isolation and comparability

Both used the same `diffuse-terraform-pilot:001` image as the Codex pilot, with
a private Nix store/database and KVM. No host home, host Nix store or daemon
socket was mounted. Only Claux and its runtime libraries were copied into the
container; its provider key was supplied through the Claux process environment,
not command arguments, configuration or an image. Child-tool environments use
Claux's normal credential sanitization. The container was stopped before
collecting regular deployment source files, then removed before private grading.
The original app, images, cluster and verifier were retained for grading.

The manifest of public files matches the earlier Codex pilot byte for byte.
The same binary was used for both Claux attempts. Each committed result includes
its binary/runner/transcript/log hashes, provider-reported usage, original plan,
config, prompt, submitted deployment, and relevant verifier excerpts. Raw
transcripts, private reasoning and full logs remain gitignored in the listed
raw-artifact directories. Requested model IDs and public pricing/capability
metadata were captured from https://openrouter.ai/api/v1/models before launch;
this does not establish which upstream endpoint OpenRouter ultimately selected.

These are individual exploratory results. Codex/GPT-6.1 Sol previously passed
all phases, but it ran through a different harness with a different output
budget, system prompt and tool behavior. This is not a controlled model ranking,
a solve-rate estimate, or proof that the task is generally hard. The Opus
submission is a useful near-miss because ordinary operation and pod replacement
worked while cold boot exposed an actual storage/permissions fault.

## Running another model

With the pilot image loaded, Linux/KVM, Docker, the built Claux binary and a
local OpenRouter credential file:

```sh
python3 scripts/pilot_terraform_claux.py \
  --model particle-ai/particle-1 \
  --binary /absolute/path/to/claux
```

The default is one 900-second attempt followed by private grading. Use
`--preflight-only` to check the environment without a paid model request.
Each invocation uses a new timestamped directory under `logs/pilots/` and a
fresh container. The image recipe is retained in the original Codex pilot's
raw directory; export public input with `scripts/export_terraform_task.py`.
Cached grading derivations are not additional fresh trials.

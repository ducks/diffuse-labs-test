# Final implementation and validation

Implemented `evaluation-integrity` as the fifth selected Harbor task. The existing
four implementations and reference solutions remain intact. Two confirmed
existing grading problems received scoped corrections: premature gateway-grader
success and Terraform root-disk infrastructure-error classification.

## Observed final results

Each row includes two clean rounds. A control succeeds when its observed result
matches its expectation: good/alternate solutions pass and incorrect ones fail.

| Task | Control executions | Expectations met | Harbor oracle rewards | Harbor no-op rewards |
| --- | ---: | ---: | --- | --- |
| Session recovery | 10 | 10 | 1, 1 | 0, 0 |
| Streaming gateway | 16 | 16 | 1, 1 | 0, 0 |
| Dataset containment | 22 | 22 | 1, 1 | 0, 0 |
| Terraform + Kubernetes | 10 | 10 | 1, 1 | 0, 0 |
| Evaluation integrity | 24 | 24 | 1, 1 | 0, 0 |
| **Total** | **82** | **82** | **10 full-reward trials** | **10 zero-reward trials** |

All **20 selected final Harbor trials** completed with **zero infrastructure
errors**, checked from Harbor's actual result JSON, not its process exit code.
Five public agent-image probes confirmed absent protected test/solution paths.
Three Terraform infrastructure-classifier regression tests passed. Python compile
checks and `git diff --check` also passed.

The fifth task accepts dictionary-based aggregation and a different SQLite
window-query implementation. Its passing isolation probe runs inside the actual
root Docker verifier while the submitted program is UID/GID 65534. Its other
controls reject the untouched importer, removing failures, merging cohorts,
hardcoded sample metrics, mutable benchmark identities, accepting extra fields,
symlink outputs, early successful exit and reward-file forgery. Protected fixtures
exercise unseen data, attribution, retries/interruption, retained history,
reordered/incremental imports and rollback after invalid batches.

## Commands actually executed

From this repository, using its pinned Nix shell/Harbor 0.25.0 installation:

```sh
python3 scripts/validate.py --container
python3 scripts/validate_gateway.py --container
python3 scripts/validate_containment.py --container
python3 scripts/validate_terraform.py
python3 scripts/validate_integrity.py --container --repeat 2
python3 scripts/test_terraform_infrastructure.py
python3 scripts/prepare_terraform_harbor.py
nix-shell --run 'python scripts/validate_harbor.py --task session-recovery'
nix-shell --run 'python scripts/validate_harbor.py --task streaming-gateway'
nix-shell --run 'python scripts/validate_harbor.py --task dataset-containment'
nix-shell --run 'python scripts/validate_harbor.py --task terraform-k8s'
nix-shell --run 'python scripts/validate_harbor.py --task evaluation-integrity'
```

The first three control commands and Terraform controls each supplied two
successful fresh rounds. Harbor commands each supplied two final oracle/no-op
pairs. Integrity had additional development rounds; the final selected round uses
the bounded-output verifier and all twelve controls. No cached Nix derivation is
counted as another fresh trial: native/Harbor Terraform runs use unique test names
and boot fresh VMs. Cached dependencies/images are reused.

`validate_submission.py` now provides the consolidated reproduction command in
README. During this work the equivalent task-specific commands were orchestrated
in smaller groups to inspect failures and serialize VM execution; this report
does not claim that the consolidated script itself supplied these recorded runs.

## Evidence

[validation/final.json](validation/final.json) is a tracked, sanitized index of
final controls, actual Harbor result paths/SHA-256s, public image IDs, and task/
validation-source hashes. Raw logs and complete results remain local and
 gitignored under `logs/`; the index does not replace those artifacts.

The final control sources are:

- `logs/final-validation/20261110T025435964108/`: both rounds for the first three tasks.
- `logs/terraform-k8s/controls-20261110T025944732523/` and
  `controls-20261110T053452675126/`: two complete matching native control rounds.
- `logs/evaluation-integrity/20261110T053456276078/`: final 24 container-control executions.

Final Harbor summaries are under
`logs/final-harbor/20261110T030006873867/`, `integrity-final-disk/`, and
`terraform-final-classified/`. Each points to its original Harbor job artifacts.

## Development failures retained separately

A Terraform canonical repeat under
`logs/terraform-k8s/controls-20261110T052310324834/` encountered virtual root-disk
write/EXT4 errors after reboot, then failed a namespace/API assertion. It remains
an unsuccessful recorded attempt and is not counted as a valid deployment
verdict. The new narrow root-disk classifier was tested against its actual log
and deterministic fixtures. Final Harbor runs exercised the corrected adapter;
normal application faults still receive reward 0.

The host uses RAM-backed `/tmp`. A client `build-dir` override was ignored because
the Nix daemon did not trust that setting; the ineffective override was removed.
No daemon/account settings were changed, and no host-storage fix is claimed.
Final Harbor verification uses isolated container filesystems/private Nix stores.
Operators of native controls must provide sufficient daemon build storage.

Earlier integrity controls exposed Boolean/integer manifest collisions and a
missing fresh extra-field fixture. Those findings and their corrections are in
[ADVERSARIAL-REVIEW.md](ADVERSARIAL-REVIEW.md); earlier failed development artifacts
remain available. They are not pooled with the final accepted control results.

## Limits

- No live coding-model pilot was run for task five. Difficulty is uncalibrated;
  reference/control success establishes grading feasibility, not hard difficulty.
- The three older shared Python tasks are not general hostile-code sandboxes
  during grading. Gateway's completion protocol blocks the confirmed premature-
  exit exploit but does not prove resistance to arbitrary protocol forgery or
  monkeypatching. Protected material is absent during the agent phase.
- Integrity has a stronger UID/file boundary and bounded artifacts/processes,
  but is not a kernel/process-abuse sandbox. Terraform controls are targeted
  operational tests, not proof against arbitrary hostile Kubernetes code.
- Terraform requires Linux/KVM, local image preparation and adequate resources.
  These are explicit prerequisites; missing infrastructure is not a scored pass.
- No live model API calls, paid infrastructure, cloud clusters or RL framework
  were introduced for this validation.

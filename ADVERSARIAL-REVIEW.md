# Adversarial review

This review distinguishes demonstrated defects and rejected controls from
unproven attacks. All data is synthetic. Exact final run evidence is indexed in
`validation/final.json`; raw logs stay under gitignored `logs/`.

## Confirmed defects corrected

1. **Streaming verifier premature success.** A submitted module containing
   `import os; os._exit(0)` terminated the old grader during import. Its shell
   entry point saw exit 0 and wrote reward 1 without executing tests. A trusted
   parent now requires exactly one successful complete-suite result with the
   expected test count, zero failures/errors/skips and child exit 0. The same
   early-exit code is a failing regression control. Existing gateway semantics,
   fixtures, reference and alternate implementations were preserved.
2. **New task's manifest equality.** Raw Python dictionaries equated JSON true
   and 1 (and integer/float equivalents). An import could therefore change a
   retained identity's manifest fingerprint. Both implementations now compare
   canonical JSON bytes. Protected tests require type-changing manifest imports
   to fail without altering either retained file, including nested values.
3. **New task's strict-field verifier gap.** A mutated implementation allowing
   extra event fields initially passed. A new event with an extra field now
   tests this independently of event-ID/attempt conflicts. Additional malformed
   identity and missing-field cases were added. The retained field-validation
   mutant fails final grading. An initial extra-field regression reused a prior
   event and only exercised conflict rejection; the corrected fixture uses a
   fresh event and trial. Earlier failed development controls remain in logs.

4. **Terraform root-disk failure misclassified as a deployment failure.** One
   repeated canonical run logged real `I/O error, dev vda`/EXT4 errors after
   reboot, then failed an API/namespace check. Its record is retained. The
   native control runner and Harbor adapter now detect that narrow harness-root-
   disk signature before interpreting task result markers. They stop as an
   infrastructure failure; Harbor emits no model reward. Three deterministic
   regression tests distinguish this from normal application readiness and
   permission failures. Both successful native rounds and this unsuccessful
   repeat remain separate evidence. A proposed per-run disk-backed build-dir
   setting was ignored by the untrusted Nix daemon and removed; no storage fix
   or account/daemon-setting change is claimed. Final Harbor runs use their
   isolated container filesystem and private Nix store.

## Executed attacks and alternatives

| Task | Tested shortcuts | Independent evidence / alternate |
| --- | --- | --- |
| Session recovery | Skip pending work; restart plan from scratch; untouched broken code | External committed receipt counts and exact transcript history fail incorrect fixes. Replaying stable idempotent requests is accepted instead of requiring reference receipt lookup. |
| Streaming gateway | Retry after emitted bytes; disable fallback; leak capacity; buffer whole response; early exit; no-op | Real HTTP plus async admission/cancellation checks; stream-priming alternate passes. Completion must come from an actually completed behavioral suite for the tested early-exit attack. |
| Dataset containment | Disable worker functionality; revoke/repair only part of the incident; blind republishing; delete audit evidence; other retained partial fixes | Real service traffic, external publications/provenance, retained receipts/history and restart checks reject these. Code-level input-root enforcement is accepted instead of requiring only reference policy configuration. |
| Terraform/Kubernetes | No workloads; volatile PostgreSQL; actual near-miss with reboot permissions fault | Real render hashes before/after acknowledged pod loss, replacement, cold boot, two namespaces, no-drift plan and teardown. Dedicated migration Job and alternative init containers both pass. |
| Evaluation integrity | Remove failures; merge cohorts; hardcode sample metrics; overwrite manifests; accept extra fields; exit zero; forge reward; redirect output to a device symlink | Protected unseen histories, original-record equality, ordering/import-sequence invariance and validation-error rollback. Dictionary and SQLite aggregation both pass. An executed isolation probe confirms candidate UID cannot read `/tests/verify.py` or write `/logs/verifier`. |

## Protected materials and timing

Actual public agent images for all five packages were launched without a network
and checked for absent test/solution paths. Harbor uploads tests only after the
agent phase and gives the solution only to the oracle. Terraform and integrity
use separate verifier environments and bounded artifact collection. Integrity
also separates its trusted grader from unprivileged candidate processes.

Session recovery uses explicit crash handshakes, not lucky sleeps. Terraform
waits for distinct replacement pod identities and a changed cold-boot ID. Its
fixtures verify prior report bytes before accepting recovery. Dataset checks
independent retained state/publication evidence rather than an empty queue.
Integrity checks existing files remain unchanged after invalid batch rejection.
Gateway checks live streaming/resource behavior rather than a final explanation.

## Limits and unverified attacks

The older three shared Python tasks are operational behavior benchmarks, not
malicious-code sandboxes during verification. The gateway completion protocol
blocks the demonstrated premature-exit exploit; it does not prove protection
against deliberate child-protocol forgery or arbitrary monkeypatching by code
executing in the grader process. No successful protocol-forgery attack was
claimed or added to the recorded results. A stronger gateway boundary would
require a separate execution protocol, beyond this narrow confirmed-defect fix.

Integrity's privilege boundary and resource limits are not a full hostile-process
sandbox (for example, process/session abuse and kernel exploits are untested).
Terraform's two implementations and three negatives are targeted operational
controls, not a proof against arbitrary malicious Kubernetes/provisioner code.
No such unexecuted attack is reported as a passing exploit. Retained tasks make
no general hard-difficulty claim; fifth-task coding-model difficulty is untested.

# Spike validation

The reference passed all six native integration phases in a fresh offline K3s
VM. The test script took 334.49 seconds, excluding host-side Nix builds. Nine
report download/content/hash checks passed, including rechecks after failures.
`validation.json` records versions, source hashes, the exact successful Nix
result, and hashes/locations of full local logs. `verification.txt` is the compact
phase record.

Validated behavior:

- Terraform creates all ten application resources from the same source and
  runtime input schema. The authenticated API accepts and renders real jobs.
- API and worker commands execute with non-root UIDs, checked inside the pods.
- The renderer acknowledges a barrier, Redis wake-ups are cleared, and that
  exact worker pod is deleted. A different, ready worker UID replaces it and
  accepted jobs complete. The visible SVG inventory has no extra files.
- PostgreSQL and Redis replacements are confirmed by new ready pod UIDs before
  retained data and new work are checked.
- A complete shutdown and boot changes the boot ID, retains report bytes, and
  leaves Terraform's detailed-exitcode plan at zero.
- A second namespace receives separate credentials, storage and records from
  the same Terraform source. Cross-namespace job lookup and token use fail.
- Destroy removes managed workloads, Services, Jobs, PVCs, derived pods and
  EndpointSlices, and associated PVs. Terraform state becomes empty. The fixture
  namespace and Secret remain. The second deployment remains healthy until its
  own destroy is tested.

## Supporting checks

The standalone cluster smoke test confirmed K3s Ready, CoreDNS rollout, and
offline initialization of the packaged Terraform Kubernetes provider. The
reference configuration passed provider schema validation. The corrected
PostgreSQL image initialized and accepted connections in an isolated Docker
smoke test with synthetic credentials and temporary storage; its container was
removed. The public interactive development expression evaluates, but was not
counted as another deployment trial.

## Useful development failures

An early smoke test needed to wait for the CoreDNS Deployment to exist before
checking rollout. Terraform's Secret mode field required an octal string rather
than a Kubernetes-style decimal value. PostgreSQL's tools also needed native
Nix store executable paths to locate their bootstrap data inside the image.

The complete deployment initially passed normal operation, worker loss and
backend pod replacement, then failed the cold boot. PostgreSQL rejected its
remounted data directory's permissions. Configuring the reference pod with
`fsGroupChangePolicy: OnRootMismatch` fixed this while retaining the cold-boot
requirement. That earlier run is retained as a development counterexample, not
counted as a final-version negative-control calibration.

The report inventory originally relied on `find`, which is not installed in the
application image; the verifier now uses Python's pathlib. Replacement checks
wait for distinct ready pod identities instead of treating a delete request as
proof of replacement. These are harness/reference fixes, not model failures.

## Targeted controls and Harbor validation

Five fresh native control trials matched their expected outcomes. The canonical
migration-Job solution and an alternate API/worker init-container migration
solution both passed all six phases. The no-op starter failed first deployment;
a reference-derived volatile PostgreSQL volume failed after backend replacement;
the unmodified Opus near-miss passed three phases and failed cold boot. These
controls exercise operational faults rather than only invalid syntax. Exact
submission hashes, failure phases and result paths are recorded in
`validation-controls.json`; raw logs remain under its recorded log directory.

The Harbor 0.25.0 Docker oracle earned reward **1.0** with all phases passing.
The no-op earned **0.0** after the required deployments were absent. Both jobs
completed with zero infrastructure errors, as checked from Harbor's result
JSON rather than its CLI exit status. See `validation-harbor.json` for job paths,
result/log hashes and the transferred deployment files. A separate-container
adapter preflight also rejected an invalid symlink submission with reward 0.

Harbor transfers only deployment artifacts into a separate fresh container;
the app, images, Nix helpers and verifier remain original. Missing KVM and native
build/VM failures without an evaluated result marker do not produce a model
reward. Unique run names force new native verification runs instead of reusing
previously successful Nix derivations. The image passed a public-files-only and
KVM preflight; its ID and public source manifest are in `environment-image.json`.

## Limits

The task now has targeted controls and a working Harbor Docker package. It
requires x86_64 Linux/KVM and local image preparation as documented in
`HARBOR.md`; other Harbor providers were not tested. This is not a solve-rate
estimate or a comprehensive adversarial calibration. Previous single-attempt
model pilots remain separate evidence: Codex/GPT-6.1 Sol passed all phases;
Claux/OpenRouter Particle failed fresh deployment and Opus failed cold boot.
Earlier frozen pilot artifacts are not rewritten by these packaging changes.

Terraform owns the application resources, not the cluster. The cluster has one
node and the reference has one replica per role. Shared ReadWriteOnce report
storage is tested only on that node. No multi-node scheduling, cloud provisioning,
TLS ingress, load testing, rolling upgrade, or high-availability claim is made.
The renderer is pure and may be retried; only visible durable outputs are checked
for duplication. Fault acknowledgement makes the queued-work interruption
observable without depending on exact pod scheduling or a lucky sleep.


## Final-submission infrastructure regression

A repeated canonical control encountered virtual root-disk write errors after
cold boot and later failed an API/namespace assertion. The retained failed run
is not counted as a valid deployment verdict. Root virtual-device I/O failures
are now recognized by `tests/infrastructure.py` in the Harbor adapter and native
control driver before interpreting task markers. They produce an infrastructure
error, not model reward 0; three deterministic tests preserve ordinary application
failures as evaluated failures. This changes no workload, reference deployment,
lifecycle assertion or expected negative-control phase. The source/runtime hashes
and final repeated checks are indexed in the root validation report.

Native host Nix builds may use a small RAM-backed temporary filesystem. The
attempted client `build-dir` override was ignored because the user is not trusted
by the daemon, so it was removed. No global Nix settings were changed. Operators
must ensure adequate daemon build space; the Harbor package instead uses its own
container filesystem and private store. Raw storage-failure evidence is retained.

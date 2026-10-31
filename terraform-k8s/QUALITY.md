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

## Limits

This is a native integration spike. There is no agent attempt, solve-rate
estimate, Harbor integration, or independently calibrated suite of good/bad
deployments. One reference pass does not establish hard difficulty or general
reliability. Successful Nix derivations may be cached; cache reuse is not a fresh
trial.

Terraform owns the application resources, not the cluster. The cluster has one
node and the reference has one replica per role. Shared ReadWriteOnce report
storage is tested only on that node. No multi-node scheduling, cloud provisioning,
TLS ingress, load testing, rolling upgrade, or high-availability claim is made.
The renderer is pure and may be retried; only visible durable outputs are checked
for duplication. Fault acknowledgement makes the queued-work interruption
observable without depending on exact pod scheduling or a lucky sleep.

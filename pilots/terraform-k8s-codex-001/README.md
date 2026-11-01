# Terraform/Kubernetes pilot 001

**One model attempt passed all six private verification phases.** Codex CLI
0.164.0 used GPT-6.1 Sol at low reasoning effort, with a 900-second limit,
web search disabled, no model retries, and no private feedback. The model
finished in **880.44 seconds**. That time includes its development builds and
VM tests, but excludes image preparation and private grading. The private test
script took **342.38 seconds**, excluding grading build time. Cost was not
measured.

## Inputs and isolation

Frozen source commit: `109a8a576e479c72bfc47f456fcf6ee1a8d5b13e`.
Run completed 2026-11-01 UTC.

The agent received the fixed application, starting Terraform declarations,
instructions, pinned toolchain/images, and public development VM. No solution,
private verifier, previous attempt, or conversation history was exported.
The container had a private Nix store/database, KVM access, two CPUs, 8 GiB RAM,
and outbound access for the model and Nix dependencies. It had no mounted host
home, Nix store, or Docker/host daemon socket. Its model credential copy and
container were removed after completion. The image contains the public
starter development VM, not a deployment solution.

The runner stopped the container before collecting the deployment. Collection
preserved regular deployment source files and the provider lock, excluding
Terraform cache/state/plan artifacts. It rejected links and bounded collected
files/bytes. Only these deployment files were supplied to the frozen private
evaluator, which retained its original application, images, VM and tests.

## What the submission did

The submission uses native Kubernetes Terraform resources: two PVCs, backend
Services, four Deployments, and an API NodePort Service. It initializes the
schema in retrying API/worker init containers rather than a dedicated migration
Job. Workloads reference runtime Secrets and use UID/GID 1000; writable /tmp
volumes and PostgreSQL data-directory permission handling were added during
the attempt. No provisioners, app replacement, or private-test special cases
were found in the submitted configuration.

Private grading passed fresh authenticated deployment/rendering; acknowledged
worker deletion with Redis wake-up loss; database/cache pod replacement;
preserved output after a full shutdown and boot; a no-drift Terraform plan;
independent namespaces, credentials and state; and destroy/PV cleanup that
preserves the second deployment. Nine report-content/hash checks were made
across the phases, including rechecks of retained reports.

## Development observations and interpretation

The agent made 66 completed shell calls and wrote its own public VM tests. Its
first copy command preserved a Nix /etc symlink; it corrected that to a
recursive dereferencing copy. K3s logged initial pause-image pull failures,
then imported the local pinned airgap images and recovered without intervention.
These were within-attempt development events, not retries or private feedback.
It also debugged writable /tmp and PostgreSQL permissions. The final response
explicitly said isolation, clean-plan and destroy checks were not completed
within its development budget; the independent grader subsequently tested them.

This is stronger evidence of a useful end-to-end task than a reference-only
pass. It remains one exploratory attempt, not evidence of a general solve rate
or hard difficulty. Runtime includes Nix/KVM development overhead; it should
not be compared directly with short code-only tasks. Negative-control
calibration and Harbor packaging remain outstanding. Original raw events,
launch script, image recipe, logs and frozen task remain gitignored under
`logs/pilots/terraform-k8s-codex-001/`; no private reasoning or credentials are
included in committed evidence.

## Reproduction

Export a fresh public workspace with:

```sh
python3 scripts/export_terraform_task.py /path/to/new-workspace
```

Reconstruct the frozen task from the source commit and grade the saved
submission with native Linux/KVM:

```sh
nix-build /path/to/frozen/terraform-k8s \
  --argstr deploymentDir "$PWD/pilots/terraform-k8s-codex-001/deployment" \
  --no-out-link --max-jobs 1 --cores 2
```

A cached derivation is not another fresh trial. New model attempts need fresh
public workspaces and separately recorded results.

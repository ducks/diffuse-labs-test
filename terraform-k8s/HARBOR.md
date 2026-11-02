# Harbor package

This task uses a K3s NixOS VM inside Harbor's Docker environment. It requires
an x86_64 Linux Docker host with working `/dev/kvm`, Nix, at least 8 GiB of
available memory for a trial, and disk space for the roughly 5 GiB base image,
Nix store and disposable VM disk. It has no cloud credentials or external
cluster requirement. Providers without KVM/device passthrough are unsupported;
there is no silent emulation fallback.

## Prepare and run

From the repository root:

```sh
# Builds the pinned public-only Nix base if absent, then the task image.
# The first build may download pinned public dependencies.
python3 scripts/prepare_terraform_harbor.py

# Use the repo's pinned Harbor installation and Docker plugins.
nix-shell --run 'uv sync --frozen'
nix-shell --run 'python scripts/validate_harbor.py --task terraform-k8s'
```

The source for image preparation is in this repository; no private registry or
pre-existing image is required. The preparation step loads local image tags
`diffuse-terraform-pilot:001` and `diffuse-terraform-harbor:v1`. `--rebuild-base`
forces a rebuild of the Nix image. These are local preparation prerequisites,
not images published to a registry. To transfer the package to another host,
run the same preparation there or explicitly transfer the prepared images.
Running Harbor without preparation on a clean host is not supported.

The image build context is generated in a gitignored log directory from an
explicit public-file export. It includes the app, starter Terraform, pinned
Nix helpers and a public development VM. Tests, the reference deployment and
pilot artifacts are not put in the agent image. The image includes its own
Nix database/store and does not mount a host home, Nix store or Docker socket.
Only `/dev/kvm` is passed through by the task's Compose override.

## Submission and verifier boundary

Harbor collects `/workspace/deployment`, excluding Terraform cache, state,
lock-runtime and plan artifacts. It starts a **separate, fresh container** and
places that artifact there. This retains the original app and fixture even if
the agent changed its development environment. Harbor uploads `/tests` only
to the verifier. The oracle gets `/solution` during its own agent phase; normal
agents do not.

`tests/run_verifier.py` copies bounded regular deployment files into a fresh
trusted fixture and starts the native verifier. Every run uses a unique Nix
test name, so a previously successful derivation cannot substitute for a new
trial. The same six behavioral phases used in native controls determine the
reward: all pass gives 1; an evaluated assertion failure gives 0. Missing KVM
or a build/VM failure without a task result marker is an infrastructure error,
not a model failure. Invalid submission links/special files and size/count
violations explicitly receive 0. No private feedback is sent to the agent.

The native and Harbor copies of the Nix verifier entry expression must match;
preparation and control validation check this. Their copies exist because
Harbor uploads the tests directory while native users build the task root.

## Controls

```sh
python3 scripts/validate_terraform.py
```

Five fresh native trials check:

- Canonical migration-Job deployment: all six phases pass.
- Alternate API/worker init-container migration deployment: all phases pass.
- No-op starter: rejected on first deployment (required workloads absent).
- PostgreSQL data on emptyDir: first deployment and worker recovery pass;
  backend replacement loses the database and fails.
- Real Opus near-miss: the first three phases pass; reboot exposes invalid
  PostgreSQL data-directory permissions.

The last two are plausible incomplete deployments, not syntax errors. They
show why checking only first startup or schema validation would be insufficient.
`validation-controls.json` records hashes, observed phases and result paths.
This is targeted calibration, not a claim of adversarial robustness against
arbitrary malicious Kubernetes workloads or a comprehensive solve-rate study.

# Deploy Docmill using Terraform and Kubernetes

Inspect the working application in `repository/` and implement its deployment
in `deployment/` using Terraform's pinned Kubernetes provider. The evaluator
provides a fresh single-node K3s cluster; Terraform owns the application stack,
not the VM or control plane. This prototype requires no cloud account or GPU.

The starting configuration declares the provider and inputs but no workloads.
Use Terraform resources, not local-exec/remote-exec provisioners or commands that
apply manifests outside Terraform's state. Only `deployment/` is submitted.
The evaluator retains the original application, images, cluster and verifier.

## Inputs and fixed environment

- `namespace`: an existing namespace provisioned for this deployment.
- `kubeconfig_path`: the supplied cluster kubeconfig.
- `api_node_port`: the NodePort on which the service must accept requests.
- `credential_secret_name`: an existing Secret, default `runtime-credentials`.
  It contains keys `api-token` and `db-password`, generated at runtime. Reference
  this Secret from workloads; do not embed credential values in source or images.

Nixpkgs, Terraform 1.15.9, Kubernetes provider 3.2.1, K3s and container images are
pinned. The cluster has local-path storage and working service DNS. The guest
has no internet route. All images are preloaded, so use `imagePullPolicy: Never`:

- `docmill-app:spike`: Python, psycopg, Redis client, Graphviz, and the fixed app.
  Commands are `python -m docmill migrate`, `api`, and `worker`.
- `docmill-postgres:spike`: PostgreSQL 17; initializes database/user `docmill`.
  Persist `/data`; provide `/run/credentials/db-password` from the Secret.
- `docmill-redis:spike`: Redis with persistence disabled. It is a wake-up cache.

The images run as UID/GID 1000. Supply appropriate writable storage and pod
security contexts. The app's `DATABASE_URL` can omit a password if `PGPASSWORD`
is supplied from the Secret. The README and source explain the other inputs.

## Observable deployment contract

- Deploy separate `api`, `worker`, `postgres` and `redis` Deployments, with
  matching `app` labels. Keep backend Services named `postgres` and `redis`,
  private to the cluster. Publish the API using the requested NodePort.
- Initialize the database schema before the API serves requests. Correctly
  wire the API, worker, database, cache, credentials and report storage.
  Set `DOCMILL_STORAGE=/reports` in both application roles; this is also the
  controller's public path for the render barrier and report inventory checks.
- Preserve the documented API. Authorized submissions return accepted IDs,
  complete to downloadable SVGs, and retain their labels and bytes. Reject
  unauthorized requests. API and worker processes must run without root.
- Accepted work must survive worker loss. PostgreSQL and rendered reports must
  survive pod replacement and a full VM shutdown and boot. Redis loss may drop
  wake-up signals but must not lose accepted jobs. Duplicate visible report
  records or files are not allowed; retrying the pure renderer is allowed.
- Applying the same configuration into another supplied namespace with its own
  credentials and NodePort must create independent state and authorization.
- After recovery, `terraform plan -detailed-exitcode` must return 0. Destroy
  must remove managed workloads, Services, Jobs, PVCs, derived pods/endpoints,
  and associated PVs, without disrupting another deployment. The fixture
  namespace, runtime Secret, and cluster system resources are not managed by you.

## Deterministic worker interruption

The prebuilt renderer includes a public test barrier under `DOCMILL_STORAGE`.
If `.render-pause` exists, it writes its pod hostname to `.render-entered` and
waits before invoking Graphviz. The controller acknowledges that marker, deletes
that exact worker pod, waits for a replacement, then removes the barrier.
The polling interval does not determine the interruption point. Do not bypass
or replace the renderer or application. Shared report storage must permit the
controller to create and remove these files through the API pod.

The fixture has a few short jobs, one node, and bounded eventual-state checks.
It does not require high availability during an outage, production sizing,
multi-node storage, a cloud load balancer, or a Helm chart. Exact scheduling,
generated pod names, and startup order beyond functional dependencies are not
graded. This is an integration task, not a claim of hard model difficulty.

## Development tools in the Harbor environment

The working directory is `/workspace`. `nix-shell shell.nix` supplies the pinned
Terraform CLI/provider for validation. For a live development cluster, build
`vm.nix -A driverInteractive` with `nix-build` and run the resulting
`bin/nixos-test-driver`. Copy `/etc/task-deployment/.` inside the guest to a
writable directory before running Terraform; the source under `/etc` is backed
by the read-only Nix store. Create a development namespace and Secret, then
set the documented Terraform variables. KVM is available on supported Linux
hosts. No host Docker socket, host home or host Nix store is exposed. Only the
files in `/workspace/deployment` are submitted to a fresh verifier environment.

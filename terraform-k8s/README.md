# Terraform + Kubernetes service deployment spike

Take the working Docmill application and write Terraform that deploys its API,
worker, PostgreSQL, Redis, schema migration and durable storage. The application
is reused from the README → NixOS prototype; this spike changes the deployment
problem rather than introducing another application or model harness.

The supplied NixOS VM runs single-node K3s. Terraform manages the application
resources through the pinned Kubernetes provider. It does not provision the
control plane, a cloud account, or a remote Kubernetes cluster. The VM imports
the cluster and application images before workloads start and needs no internet
route. Host-side Nix builds may download pinned inputs.

## Run the reference

From the repository root on Linux with Nix and usable `/dev/kvm`:

```sh
nix-build terraform-k8s \
  --argstr deploymentDir "$PWD/terraform-k8s/solution" \
  --no-out-link --max-jobs 1 --cores 2
```

`deployment/` is the starting submission; `solution/` is the reference.
Terraform JSON configuration is native Terraform syntax, so the reference uses
`main.tf.json`; a submission may use ordinary `.tf` files. Provider and Terraform
versions are fixed. The local provider checksum comes from the pinned Nix build,
not an independently downloaded registry binary.

The verifier boots a fresh cluster and checks:

1. Terraform apply creates a working authenticated report pipeline.
2. A worker pod is killed after it acknowledges a pause before rendering;
   accepted work completes on its replacement even after Redis wake-ups are cleared.
3. Database and cache pods can be replaced without losing report bytes.
4. A cold VM boot retains reports, and Terraform's subsequent plan has no changes.
5. The same configuration creates separate state and credentials in another namespace.
6. Terraform destroy removes managed resources and associated PVs, preserving
   the other deployment until it too is destroyed.

The fault boundary is an explicit acknowledgement, not a lucky sleep. Scheduling
and startup timing are handled with bounded eventual-state assertions. The
spike has one node: same-node shared ReadWriteOnce storage is sufficient. It
does not claim multi-node availability or exactly-once renderer execution.

## Development VM and tools

```sh
nix-build terraform-k8s/vm.nix -A driverInteractive --no-out-link
# Run the returned bin/nixos-test-driver, then cluster.start().
# cluster.shell_interact() opens a root shell in the disposable VM.
```

Inside that VM, a development setup can use:

```sh
mkdir -p /root/deployment
cp -r /etc/task-deployment/. /root/deployment/
chmod -R u+w /root/deployment
kubectl create namespace playground
kubectl -n playground create secret generic runtime-credentials \
  --from-literal=api-token=development-only \
  --from-literal=db-password=development-only
export TF_VAR_namespace=playground
export TF_VAR_kubeconfig_path=/etc/rancher/k3s/k3s.yaml
export TF_VAR_api_node_port=30080
terraform -chdir=/root/deployment init
terraform -chdir=/root/deployment apply
```

For host-side Terraform syntax/schema work, `nix-shell terraform-k8s/shell.nix`
provides the same CLI and Kubernetes plugin. It does not point at a host cluster
or create cloud resources. The Terraform package's license is enabled only in
this spike's Nix import.

## Status and limits

This is a native integration spike, not a packaged Harbor task or a calibrated
five-task submission. No model attempt or solve-rate claim is included. Keep
the verifier and reference outside a future agent's workspace. The initial
cluster/DNS/provider smoke test and schema validation are separate from the full
lifecycle result. See `QUALITY.md` for the actual validation scope.

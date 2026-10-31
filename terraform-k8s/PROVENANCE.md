# Provenance

The unchanged application is Docmill from this repository's
`readme-to-nixos/repository`, introduced in commit `80f98db`. It uses PostgreSQL
for durable accepted jobs, Redis for optional wake-ups, and Graphviz to produce
SVG report files. The Kubernetes spike adds fixed container packaging and an
explicit renderer barrier; it does not ask an agent to repair the app.

Nixpkgs is pinned to revision `9fbb54b33e91ee4ca368e35a78e0613c720600b3`
with a content hash in `nixpkgs.nix`. Terraform 1.15.9 and its Kubernetes
provider 3.2.1 come from that pin. K3s and its air-gap bundle also come from
that revision. App/PostgreSQL/Redis archives are locally constructed Nix
derivations; no mutable registry tag is fetched at runtime. The `:spike` names
refer to those preloaded archives in a fresh disposable cluster.

Air-gap setup and provider behavior were checked against upstream documentation
and the pinned NixOS module/provider source:

https://docs.k3s.io/installation/airgap

https://docs.k3s.io/add-ons/import-images

https://registry.terraform.io/providers/hashicorp/kubernetes/3.2.1/docs

This is an original task fixture, not an adaptation of a confidential incident
or a copy of another benchmark. Runtime credentials and workload labels are
synthetic and generated independently for each deployment.

# Validation scope

This is a native Linux/KVM prototype. The public task supplies a working
application and asks for a NixOS deployment module. It does not ask the agent to
repair application code. Nixpkgs is pinned by revision and content hash.

The evaluator boots two independent NixOS machines with separate disks. It
checks authenticated Graphviz reports through the public API, non-root application
processes, runtime secret and report permissions, durable queued work after Redis
loss, PostgreSQL/Redis recovery, worker replacement after SIGKILL, persistent
reports after a full shutdown and boot, independent deployment credentials and
state, API reachability between machines, and private database/cache ports.
Checks inspect behavior and process state rather than matching module text.

The control suite accepts both the reference module and a variant that supplies
Graphviz through a wrapped Python executable instead of a systemd PATH. Negative
controls remove the deployment, renderer, worker boot activation, persistent
report storage, or worker restart policy. A negative result counts only when it
fails in the intended test phase; evaluation/build failures do not count as
successful negative controls.

Run locally:

```sh
nix-shell --pure --run 'python scripts/validate_nixos.py'
```

Each run freezes a task snapshot and records source hashes, individual logs,
timings, expected outcomes, and actual outcomes under `logs/readme-to-nixos/`.
`validation.json` alongside this document records the reviewed control outcomes.
Full logs and VM artifacts remain local and gitignored.

The final reference was also validated with QEMU's restricted user network
enabled. The test VLAN still permits communication between the guests. Guest
DHCP is disabled and the verifier asserts the absence of an IPv4 default route;
host-side dependency builds can still download pinned Nix inputs.

## Limits

These controls establish useful grading behavior, not model difficulty. No model
has attempted this task yet. There is no Harbor integration or isolated agent
runner; evaluating arbitrary submitted Nix code needs an appropriately isolated
builder. The public workspace exporter excludes evaluator and reference files,
but is not itself a security boundary.

The fixture uses local PostgreSQL and Redis, synthetic reports, two 1 GiB guests,
and bounded recovery deadlines. It does not evaluate production sizing, TLS,
backups, high availability, or arbitrary malicious modules. Nix may reuse cached
successful test derivations; a cached result is not an independent fresh trial.

# README → NixOS prototype

Inspect the development README and source in `repository/`, then submit one
NixOS module. The app is a real PostgreSQL/Redis-backed report pipeline with an
external Graphviz renderer. The task evaluates a booted deployment rather than
matching a reference configuration's text.

`instruction.md` is the public task contract. `deployment.nix` is the empty
starting submission. `solution/deployment.nix` and `tests/` are evaluator-only
materials, not part of the agent's starting repository.

## Run

On a Linux host with Nix and readable/writable `/dev/kvm`:

```sh
nix-build readme-to-nixos \
  --argstr moduleFile "$PWD/readme-to-nixos/solution/deployment.nix" \
  --no-out-link --max-jobs 1 --cores 2
```

Replace the module path to evaluate another submission. Nixpkgs is pinned by
revision and content hash in `nixpkgs.nix`; no flakes or global pip tools are
required. The first build may download substantial NixOS dependencies. Successful
Nix test results are cached by derivation identity, so distinguish a cached
validation from a fresh independent run. Do not delete other Nix store paths or
VM artifacts merely to force a rerun.

## Public workspace and development VM

Export the material to give a coding agent into a new directory:

```sh
nix-shell --run 'python scripts/export_nixos_task.py logs/docmill-agent-workspace'
```

The export includes the instruction, empty module, pinned source helpers, public
application, and `vm.nix`. It excludes `tests/`, `solution/`, local state, virtual
environments, and Python caches. The public development VM contains no grading
assertions or reference configuration:

```sh
cd logs/docmill-agent-workspace
nix-build vm.nix -A driverInteractive --no-out-link
# Run the returned path's bin/nixos-test-driver for an interactive Python REPL.
# Use dev.start(), dev.wait_for_unit("multi-user.target"), and dev.shell_interact().
```

Provision the development credential as described by the task before expecting
the API to become ready. Both public and grading VMs lack an internet default
route; build-time Nix dependency downloads remain available on the host. Source
packaging excludes development caches and local report/state directories.

The two test VMs use 1 GiB RAM and one core each. They are disposable and use
separate fresh writable disks. The test checks initial boot, runtime credentials,
authenticated end-to-end reports, persistence, dependency recovery, worker
supervision, a full guest reboot, a second independent deployment, and external
network reachability. See `QUALITY.md` for actual validation results once run.

This is a **native NixOS task prototype**, not a packaged Harbor Docker task.
A model pilot must receive only `instruction.md`, the application repository,
and the starting module. Keep the verifier and reference module outside that
workspace. Agent isolation/Harbor integration and measured solve difficulty are
separate follow-up work; none is claimed by a passing reference deployment.

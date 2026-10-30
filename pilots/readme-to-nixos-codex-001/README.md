# README → NixOS pilot 001

Frozen task commit: `80f98dbe489d1d2cd1754c299fba99d531b19c0a`.
Run completed 2026-10-30 UTC.

**One model attempt passed all six private verification phases.** Codex CLI
0.164.0 used GPT-6.1 Sol at low reasoning effort, with web search disabled, a
600-second limit, and no model retries or private test feedback. Agent execution
took **264.94 seconds**, including its development builds and VM tests. Container
image preparation and subsequent private grading are excluded from that time.
Private test-script execution took 81.65 seconds; this is not total grading
build time. Cost was not measured.

## Isolation and evidence

The model received the public exported workspace in a fresh Docker container:
instructions, empty module, fixed application, pinned Nix helpers, and the public
development VM. It received no reference module, private verifier, conversation
history, or previous attempts. The container had its own Nix store/database,
KVM access, two CPUs, 6 GiB RAM, and outbound network access for model requests
and Nix dependencies. No host home, host Nix store, or daemon socket was mounted.

The image prewarmed the empty public development VM and generic dependencies.
It contained no application deployment solution. The model read Nixpkgs service
modules and wrote its own VM tests. Review of its 34 shell commands found no
private-material access. The final module was inspected before the frozen
private evaluator built and booted two fresh machines. Grading received only
the module, retaining the original application and tests.

The submitted implementation uses packaged Python/Graphviz, separate non-root
API and worker units, private systemd state directories, runtime secret loading,
service restart policies, PostgreSQL ownership, and loopback Redis. It serializes
the roles' schema migrations with `flock`; this differs from the reference's
dedicated migration unit. It does not replace application behavior or test IDs.

Verification passed authenticated rendering, local permissions, durable queued
work after Redis loss, backend recovery, automatic worker replacement, identical
reports after a cold boot, separate state/credentials on a second deployment,
cross-machine API access, and private backend ports. `verifier.txt` retains the
phase summary; `deployment.nix` is the unmodified submission.

## Harness issues

Three pre-model setup checks failed while correcting container permissions and
the preflight store-path query. None invoked the model. They are setup failures,
not model failures or model retries, and their original records remain local.

After successful model completion, the primary module was collected correctly,
but copying an optional full workspace archive failed on destination permissions.
The original runner summary therefore records an infrastructure error. We retain
that record rather than silently rewriting it. The intact module, final response,
event stream, and completed private grading support an evaluated pass despite
the secondary archive failure. No model call was repeated to repair collection.
The disposable container and its credential copy were removed by the runner.

## Interpretation and reproduction

This version is solvable by this model at low reasoning effort in a few minutes.
One exploratory pass does not establish a general solve rate, reliability, or
hard difficulty. Its time is not directly comparable to the earlier Python task
pilots, because it includes Nix builds and VM execution.

`plan.json`, `source-manifest.json`, and `result-summary.json` retain settings,
input hashes, outcome, usage, artifact hashes, and the exact Nix result path.
Full model events, launch script, image recipe, setup failures, and frozen task
remain gitignored under `logs/pilots/readme-to-nixos-codex-001/`. Private grading's
raw log is retained there as `verifier.log`. No credentials or private model
reasoning are committed.

The frozen task can be reconstructed from its source commit. Grade the saved
submission against that version using native Linux/KVM:

```sh
nix-build /path/to/frozen/readme-to-nixos \
  --argstr moduleFile "$PWD/pilots/readme-to-nixos-codex-001/deployment.nix" \
  --no-out-link --max-jobs 1 --cores 2
```

A successful derivation may be reused from Nix's cache. Reuse is not another
fresh trial. New model attempts should use fresh public workspaces and keep
their results separate from this pilot.

# README → NixOS: deploy an unfamiliar application

The `repository/` directory is a small working application, Docmill. Its README
explains local development. Inspect that README and the source, then write
`deployment.nix`: a self-contained NixOS module that deploys the application.

The module receives the normal NixOS arguments plus `appSource`, an immutable
path to the repository. Use the provided `pkgs`; the evaluator pins Nixpkgs.
Only your module is submitted. Do not modify the application, fetch another
application implementation, depend on your working directory, or assume that
manual commands on a previous machine will be repeated.

## Production contract

- Expose the documented authenticated HTTP API on port 8080, reachable from
  another machine. Requests and rendered reports must retain the application's
  original behavior. Unauthorized requests must fail.
- Run both application roles under non-root identities. Provide manageable
  `docmill-api.service` and `docmill-worker.service` units that start on boot.
  Include their actual runtime dependencies, schema initialization, and private
  writable state. Do not install Python packages or fetch application code at
  service startup.
- Operate PostgreSQL and a Redis instance through the NixOS service modules.
  Their maintenance units are `postgresql.service` and `redis-docmill.service`.
  They serve local application processes and must not be reachable from other
  machines. Use a database/user named `docmill` and a system group `docmill`.
- Runtime provisioning creates `/run/secrets/docmill-api`, owned by root and
  group docmill with mode 0640, after the VM reaches multi-user.target. Its
  contents are the HTTP bearer token. The API must become ready within 90
  seconds of provisioning; do not bake a token into a derivation or Nix store
  path. Provisioning supplies this ephemeral file again after reboot.
- Accepted reports must complete within 30 seconds under the test workload.
  Persist the database and rendered files. Existing reports must remain
  downloadable with identical bytes after dependency restarts and a full VM
  reboot. Report state must be private from unrelated local users.
- Queued jobs must complete after Redis wake-up data is lost. After restarting
  PostgreSQL or Redis, the application must recover without manual repair.
  A killed worker must be replaced automatically within 30 seconds. Deliberate
  administrator stops are restarted by the test controller, not by your unit.
- The same submitted module must initialize a second independent clean machine
  with its own credential and data, without copying warm state or relying on
  commands you ran on the first one.

You may add packages, helper scripts, users, migrations, proxies, and additional
units in the module. Internal design is yours; the observable application and
operational contract are the grading boundary. The test workload has two small
machines and a few short reports, not production load. Availability during a
backend outage is not required; recovery and retained data are.

## Evaluation environment

This prototype uses native NixOS QEMU integration tests on Linux with KVM.
The evaluator supplies VM boot/network instrumentation and basic diagnostic
utilities, but no application services. The application source remains fixed.
Tests generate credentials and report inputs at runtime. They boot independent
VMs from the submitted module; there is no deployment repair function to call.

The task requires no model API calls. Host-side dependency downloads can occur
while Nix constructs the pinned closures; VM startup must not require internet.
This native prototype is not yet a Harbor Docker task. Its verifier runs on the
host, so it does not require nested virtualization inside a Docker container.

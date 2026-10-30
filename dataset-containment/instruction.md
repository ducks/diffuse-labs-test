# Contain the dataset-worker incident without losing accepted work

A security alert found unexpected file reads and recurring exports on a dataset
platform. Normal previews still process, but some jobs interrupted during the
incident have durable outputs without queue acknowledgements. Health endpoints
remain green. Restarting the worker has not resolved the incident.

Implement a reusable deployment repair in `/app/repair.py` and correct the
worker in `/app/service.py`. The repair entry point is `repair(root)`, where
`root` is a `pathlib.Path` to a provisioned deployment. Each test deployment has
fresh synthetic credentials, dataset IDs, job IDs, ports, and existing state.
Your procedure must inspect that deployment; do not hardcode fixture identities
or manufacture replacement datasets/results. The harness calls your repair
while real client traffic and the existing services are active.

## Required outcome

- Dataset previews may read files only inside the deployment's worker input
  directory, including when paths contain traversal or point through symlinks.
  Legitimate previews must still return the original file contents.
- All exposed access and refresh capabilities must stop working, including
  access minted from a disclosed refresh credential. Supply the worker with a
  functioning replacement identity. Preserve the unrelated client's original
  access, tenant boundaries, and datasets.
- Stop unauthorized recurring exports without stopping legitimate reporting.
  Keep existing audit and export evidence; hiding or deleting evidence is not
  containment.
- Recover interrupted jobs using their existing matching durable outputs.
  Every accepted job needs exactly one actual output, one publication event,
  and a matching queue acknowledgement. Preserve historical receipts and
  results. Don't discard backlog, fabricate acknowledgements, or blindly
  republish an already committed external effect.
- The repair must handle the same interruption for future jobs, not only clean
  up today's rows. A failed acknowledgement can leave an output committed while
  its queue job remains pending. A process restart does not erase that output.
- Preserve client reads and submissions during `repair(root)`. Each accepted
  live job must complete within 15 seconds. You may briefly replace the worker;
  do not stop/restart the API, identity, output, or scheduling services during
  repair, or revoke the original client's credential.
- Persist code, configuration, identity, and state changes. Verification restarts
  the worker process and recreates the protected core HTTP servers, then
  introduces more ordinary and interrupted work. The repair procedure is not rerun after these restarts.

Only `/app/service.py` and `/app/repair.py` are editable submission files.
`service.py` supplies the worker role; its API, identity, output, and scheduler
implementations are shown for context, but these other services run from the
provided runtime outside your submission. Changes to their copied code do not
change the actual protected services. You may add helpers within the two files.

## Deployment and investigation tools

The readable `/opt/task-service` directory contains the public service and
provisioning code, database schemas, and deployment control helper. The layout
under `root` mirrors a Linux installation:

```
etc/dataset-platform/worker.env
etc/dataset-platform/client.json
var/lib/dataset-api/state.sqlite3
var/lib/dataset-identity/auth.sqlite3
var/lib/dataset-output/receipts.sqlite3
var/lib/dataset-worker/identity.json
var/lib/dataset-worker/incoming/
run/deployment.json
run/worker.pid
run/worker.log
```

Use `platform_runtime.restart_worker(root)` after persisting a worker change.
It stops only that worker, reloads `worker.env`, launches the submitted
`service.py`, and waits for HTTP readiness. Worker environment values contain
its actual file paths and loopback service URLs. This helper and the other
provided runtime files are not editable. It does not restart core services.
SQLite state is available for the repair procedure to inspect and update.
Existing schema and public HTTP behavior must remain compatible.

You can import `platform_service` and `provision` to construct local fixtures
and exercise real HTTP requests. `platform_service.call` is the supplied HTTP
client helper; inspect it and the service handlers for their public contracts.
`provision.initialize(Path(...))` creates synthetic files/databases; its default
configuration models a Linux installation, so local scratch fixtures require
paths and loopback ports appropriate to that scratch root.

This is an incident-inspired **code repair procedure**, not a live production
intrusion exercise. All data and credentials are synthetic and all services use
loopback; no external systems, exploits, packages, or model calls are required.
One worker processes jobs at a time. Files aren't concurrently swapped by a
hostile local writer; ordinary traversal, sibling-prefix paths, and symlinks
still must be contained. Worker process restarts are tested; machine power failure and
full host reboot are outside this Docker task. Live-traffic requirements apply
to the repair turn, excluding verifier-controlled service restarts.

# Origin and adaptation

This task adapts Jake Goldsborough's existing Replaybook scenario rather than
claiming an independent reconstruction of the original intrusion.

- Source repository: `ducks/replaybook-infra`.
- Local source worktree: `~/dev/replaybook-infra-containment`.
- Branch inspected: `feature/dataset-worker-containment`.
- Pinned source commit: `f8e2936c57b6dc56e9f31e0986a698132e73d85d`.
- Scenario: `037-dataset-worker-containment`, version 4.
- Original code license: MIT, reproduced in `LICENSE`.

The public service and provisioner are adapted from that commit's `app/`.
The private lifecycle assertions and live-traffic witness are adapted from its
controller files. The reference worker reconciliation follows that scenario's
oracle. File paths, process controls, and scoring packaging are adapted for
standalone Docker/Harbor execution. The source worktree has not been modified.

## Preserved behavior

Real loopback HTTP services, randomly provisioned synthetic identities and
state, file-boundary probes, access and refresh revocation (including a derived
access token), unauthorized schedule containment, unrelated client access,
legitimate reporting, retained audit evidence, durable output receipts,
interrupted-job recovery, live client traffic during the repair procedure, and
verification after actual worker-process replacements and recreated core HTTP servers.

The verifier uses the supplied runtime for protected API, identity, output, and
scheduler services. Submitted copies of their code are not used to score the
repair. The worker is a separate process running the submitted worker code.
The repair procedure is also a separate process. Controller-owned observations
and traffic reports are kept outside the deployment root. Publication provenance
is recorded by the verifier as the real output service responds, so inserting
new receipt rows alone cannot satisfy the output contract.

## Deliberate differences

The agent writes a repeatable `repair(root)` procedure and worker patch against
public service code. Deployment fixtures and live traffic start during grading,
not throughout the model's preceding code-authoring turn. The live-client
requirement covers execution of that procedure. Services are regular Linux
processes in one disposable container, rather than isolated NixOS systemd
services with separate service users and an external SSH controller.

Actual worker-process restarts are tested. The protected API, identity, and
output services run in trusted verifier threads; their HTTP servers are closed
and recreated at the same ports during restart checks. They are not separate
service processes. This cycle runs twice and is **not called a host reboot**.
The NixOS host-reboot guarantee, service-user isolation, and controller/guest VM
security boundary are not claimed for this port. One publisher/worker is in
scope; malicious runtime tampering, ptrace attacks on the verifier, and hostile
filesystem races are not the intended submission model.

The original branch's oracle and Particle pilot results apply to the original
scenario and harness only. They are not scores or difficulty evidence for this
adapted task. This port needs its own validation and model pilots.

## Public incident context

The scenario is fictional and inspired by documented trust-boundary and
credential failures. It uses a constrained local file-read boundary; it does
not reproduce the original exploit chain, RCE, lateral movement, command and
control, or any real credentials or company infrastructure.

https://huggingface.co/blog/agent-intrusion-technical-timeline
https://openai.com/index/hugging-face-incident-and-the-road-ahead/

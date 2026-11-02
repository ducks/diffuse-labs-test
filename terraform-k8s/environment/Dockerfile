# Build/load this pinned Nix base with scripts/prepare_terraform_harbor.py first.
FROM diffuse-terraform-pilot:001
USER root
RUN rm -rf /workspace && mkdir -p /workspace /opt/task-fixture /logs/verifier
COPY workspace/ /opt/task-fixture/
RUN cp -r /opt/task-fixture/. /workspace/ && chmod -R u+w /workspace
WORKDIR /workspace

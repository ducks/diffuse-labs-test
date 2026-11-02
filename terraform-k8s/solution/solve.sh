#!/bin/sh
set -eu
rm -rf /workspace/deployment
mkdir -p /workspace/deployment
cp /solution/main.tf.json /workspace/deployment/main.tf.json
cp /opt/task-fixture/deployment/.terraform.lock.hcl /workspace/deployment/.terraform.lock.hcl

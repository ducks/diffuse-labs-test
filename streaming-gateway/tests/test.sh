#!/bin/sh
set -eu
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
python /tests/run_verifier.py
echo 1 > /logs/verifier/reward.txt

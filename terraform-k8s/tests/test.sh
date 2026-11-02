#!/bin/sh
set -eu
mkdir -p /logs/verifier
rm -f /logs/verifier/reward.txt
python3 /tests/run_verifier.py

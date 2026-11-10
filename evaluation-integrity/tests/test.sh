#!/bin/sh
set -eu
mkdir -p /logs/verifier
rm -f /logs/verifier/reward.txt
chmod 0700 /tests /logs/verifier
export REQUIRE_ISOLATION=1
python /tests/verify.py

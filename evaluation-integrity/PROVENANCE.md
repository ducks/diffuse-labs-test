# Design provenance and scope

Inspired by Replaybook's explicit benchmark/cohort versions, model/provider and
harness provenance, immutable execution snapshots, retained attempts, and
separation of evaluated outcomes from unavailable runs:
https://github.com/ducks/replaybook

This task is a new, synthetic JSON evaluation service. It copies no Replaybook
runtime, private runs, model transcripts or real credentials. Its CLI, data
fixtures, reference implementations and verifier are independent. Familiarity
with Replaybook is unnecessary. Its documented latest-attempt rule is a local
contract, not a claim that Replaybook uses this exact aggregation policy.

The starting implementation combines four defects: cohort leakage, wrong
model/harness/version grouping, retry double counting, and mutable registry
identities. Explicit handling of interrupted and unavailable attempts makes
those errors observable. Historical records remain append-only even when a
newer retry supplies the scored outcome.

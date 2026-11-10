# Evaluation integrity incident

The comparison service claims that a new agent improved dramatically. Operations
noticed that held-out results resemble development scores and imports sometimes
change old reports. Repair `/app/pipeline.py`. Preserve the CLI and JSON contract
below; only this file is collected for grading. Use Python's standard library.
Do not replace the task with fixed output or discard inconvenient records.

## CLI and persistence

`python pipeline.py --input batch.json --state ledger.json --output report.json`

The input and existing state are JSON objects. A missing state means an empty
ledger. State has exactly `schema_version: 1`, `benchmarks`, and `results`.
An input batch has `benchmarks` and `results` arrays. The output state must retain
all accepted registry entries and result events, including failed, interrupted,
and unavailable ones. No source file may be rewritten. State and report must be regular files of at most 4 MiB each. Each successful command
writes deterministic JSON state and report; success is exit 0.

A benchmark entry has exactly `id`, `version`, `cohort`, `manifest`. IDs and versions
are nonempty strings, cohort is `development` or `held-out`, and manifest is a
JSON object. The identity is `(id, version, cohort)`. Its manifest is immutable:
reimporting the same identity and manifest is idempotent; changing that manifest
is an error. Different versions/cohorts may have different manifests.

A finalized result event has exactly:
- `event_id`, `trial_id`, `model`, `harness`: nonempty strings;
- `benchmark_id`, `benchmark_version`, `cohort`: an existing registry identity;
- `attempt`: a positive integer (not a Boolean);
- `status`: `passed`, `failed`, `interrupted`, or `unavailable`.

Validate all batch entries before changing state or report. Unknown identities,
invalid fields, conflicting event IDs or conflicting outcomes for one logical
attempt are errors: exit nonzero and leave both existing files byte-for-byte
unchanged. Identical repeated event IDs are idempotent. Different event IDs for
the same identical attempt must both remain in history but count only once.
A logical trial is `(benchmark identity, model, harness, trial_id)`; an attempt
adds its positive attempt number. Same-attempt events must agree on every field
except `event_id`. New retries append; they never delete prior events.

## Report contract

The report is `{"schema_version": 1, "groups": [...]}`. Each group has exactly:
`benchmark_id`, `benchmark_version`, `cohort`, `manifest_sha256`, `model`, `harness`,
`trials`, `passed`, `failed`, `interrupted`, `unavailable`, `evaluated`, `pass_rate`.
Only groups with result events are included. Sort groups by benchmark ID,
version, cohort, model, then harness (ordinary string order).

The manifest fingerprint is SHA-256 of UTF-8 JSON serialized using
`sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False`.
Only the **highest-numbered attempt** for each logical trial contributes to its
group, regardless of status. `trials` counts those logical trials; `evaluated`
is passed + failed + interrupted. Interrupted attempts remain explicit and count
against success; unavailable attempts remain explicit but are excluded from the
pass-rate denominator. `pass_rate = passed / evaluated`, or null if evaluated=0.
Do not pool cohorts, models, harnesses, benchmark versions or manifest identities.

Sort state benchmarks by (id, version, cohort), and state events by event_id.
Use `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False,
allow_nan=False) + "\n"` for both written files. Identical retained events must
produce identical file bytes regardless of batch/order, including incremental
imports. A batch may supply results for definitions already in retained state.
The sample batch illustrates the format; verification uses other datasets,
orderings and import sequences. Public benchmark records contain no secrets.

Scope: one writer, bounded local JSON files. Concurrent writers, power loss
between the two file replacements, malicious storage tampering and arbitrary
filesystem I/O faults are outside the contract. Validation failures must be
transactional. Separate temporary files plus replace are sufficient for writes.

Grading bounds: one collected regular Python file, at most 256 KiB. Each CLI
invocation gets a five-second wall limit, three CPU seconds and 256 MiB address
space; the protected batches contain fewer than 1,000 events. No network access
or third-party dependencies are needed. Candidate processes cannot read grader
fixtures or write reward files.

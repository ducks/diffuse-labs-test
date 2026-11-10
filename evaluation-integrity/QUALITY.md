# Evaluation-integrity scope and controls

The agent repairs a standalone standard-library JSON importer, not Replaybook.
The four interacting faults and exact input/output rules are public in
`instruction.md`. Finalized results, benchmark registries and report files are
separate; report scores cannot stand in for retained history.

The protected verifier imports no submission or reference implementation.
It computes expected aggregates by scanning each benchmark/model/harness group,
then independently selecting the highest attempt of each trial. A small explicit
boundary fixture checks passed/failed/interrupted/unavailable denominators.
Other deterministic synthetic fixtures vary names, manifests, models, harnesses,
cohorts and retry histories. Reordered, incremental and duplicate ingestion must
produce identical state and report bytes. Invalid imports must leave both files
unchanged, including when a valid new record precedes the offending record.

The dictionary-based canonical implementation and a SQLite window-query
implementation both satisfy the contract. Controls retain valid ingestion while
selectively dropping failed history, merging cohorts, returning the public
sample's metrics, mutating registry identities or tolerating extra event fields.
The untouched legacy importer, exit-zero and reward-forgery shortcuts are also
rejected. An isolation-probe implementation checks that protected files really
are unreadable and reward directories unwritable under the submission UID.

Independent critique found and reproduced two development defects. Raw Python
manifest equality treated true and 1 as equal despite different fingerprints;
canonical serialization now defines equality, with nested Boolean/integer and
integer/float regression fixtures. A field-validation mutant initially passed
because no fresh event carried an extra field. A genuinely new extra-field event
now tests that contract independently of duplicate/conflict rejection. Final
controls and Harbor validation are indexed in the root `VALIDATION.md`.

Harbor uses a separate verifier container and transfers only `pipeline.py`.
The root-owned `/tests` and `/logs/verifier` directories are mode 0700 before
submissions execute. Each invocation runs as UID/GID 65534 with no supplementary
groups, a small environment and bounded CPU, address space, files/descriptors
and wall time. Read-only inputs are created in a root-owned directory outside
the writable submission directory. Output artifacts must be bounded regular files;
a device-symlink control is rejected before parsing. The trusted parent compares actual output and retained data;
no self-reported grade is accepted. Child process groups are terminated afterward.
Local non-root tests establish behavior only; the Docker/Harbor runs establish
the permissions boundary. This is not a general hostile-process sandbox: process
abuse, kernel attacks, concurrency and storage power-loss semantics are outside
scope. Single-writer validation-error atomicity is in scope and tested.

No model difficulty or performance claim follows from reference/control passes.
The task has not had a live coding-model pilot. No private benchmark outputs,
provider secrets, model transcripts or paid infrastructure are used.

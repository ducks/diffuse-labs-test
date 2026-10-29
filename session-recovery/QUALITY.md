# Quality-control record

Initial local validation on 2026-10-28; full integration validated 2026-10-29.

Local command:

```sh
nix-shell --pure --run 'python scripts/validate.py'
```

Pinned shell interpreter: Python 3.14.7. No third-party Python dependencies.

| Control | Result | Why it matters |
| --- | --- | --- |
| Canonical receipt-lookup recovery | Pass | Completed receipts recover missing results while preserving call IDs |
| Alternative idempotent request replay | Pass | The verifier accepts a materially different correct recovery strategy |
| Original code with no changes | Fail | An interrupted action can execute twice; completed resumes add another final message |
| Discard and skip pending action | Fail | Can lose an unexecuted action and its required history/result |
| Restart the entire plan | Fail | Repeats prior effects and rewrites persisted conversation history |

Each control runs the same seven test methods. The crash-boundary method has
nine subcases (three boundaries for each of three actions); the repeated-crash
method kills and resumes the same session four times. Test fixtures use a
different plan from the agent's example and two sessions sharing one tool store.

Subprocess handshakes select exact crash points; no sleep is used to guess when
an external operation committed. SIGKILL prevents graceful shutdown from hiding
the persistence gap. All state lives in fresh temporary directories.

These results establish functional positive/negative controls, not solve-rate
or difficulty calibration. No actual model attempts have been measured yet.
The task's `hard` metadata is provisional until those pilots are run.

## Container and Harbor results (2026-10-29)

`nix-shell --run 'python scripts/validate.py --container'` runs all five
controls through the actual `/tests/test.sh` entry point. Both positive controls
receive reward 1 and all three negative controls receive reward 0.

`nix-shell --run 'python scripts/validate_harbor.py'` uses repo-local Harbor
0.25.0 with the locked dependency graph:

| Harbor agent | Completed trials | Trial errors | Reward |
| --- | --- | --- | --- |
| oracle | 1 | 0 | 1.0 |
| nop | 1 | 0 | 0.0 |

The container interpreter is Python 3.12.8, with its base image pinned by digest.
Both Python versions pass the behavioral controls. Tests and solutions are
mounted separately and do not appear in the image's `/app` workspace.

Early Harbor attempts failed due to Docker plugin selection and a read-only
Docker config. The Nix shell now selects matching Nix-provided plugins and uses
writable repo-local Docker state. Infrastructure errors are explicitly rejected
by the Harbor validation script, even when the CLI returns exit code zero.

Machine-readable detailed results are in `logs/validation.json`,
`logs/validation-container.json`, and `logs/validation-harbor.json`.
No actual coding-agent solve-rate pilots have been run. Difficulty remains
provisional. The shell and container have been tested on Linux, not macOS.

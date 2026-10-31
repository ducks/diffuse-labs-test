# Hyprland / Claux vision pilot 001

One exploratory attempt using `deepseek/deepseek-v4-flash-vision-exp` through
Claux and OpenRouter. It received two visual iterations with fresh one-shot
contexts, the saved configs, three target screenshots and three current
screenshots, and the previous iteration's outcome. Each iteration had a
180-second wall-clock limit and **12 model rounds**. Private grading ran once,
after both iterations; no private feedback reached the model.

**Evaluated failure:** both iterations exhausted the 12-round cap without
changing any of the six config files. They made 18 and 15 successful tool calls,
respectively. The model inspected source files and measured screenshot colors
and geometry, but did not save a configuration change. The submitted desktop
passed the existing functional checks and failed visual grading as expected for
the unchanged starter. This is not a claim that the task is hard.

Provider-reported cost for these two completed invocations totals **$0.04868048336**.
This excludes an earlier transport-unavailable attempt whose cost is unknown.
`result-summary.json` retains timings, reported usage, budget outcomes, final
file hashes, and per-region errors. `submission/` contains the exact six files.

## Isolation and limits

The editing process used Bubblewrap filesystem and PID namespaces. Host home,
private tests, reference config, and the host Nix store were absent. Only public
task files, a temporary Claux home, artifacts, and system tools were exposed.
Outbound network access allowed OpenRouter requests; the key was inherited in
the process environment rather than embedded in arguments or configuration.
The host supplied fixed public previews and kept the final evaluator separate.

The round cap was a harness choice, not a model/provider requirement. It was too
restrictive to establish task difficulty. Claux normally permits 200 rounds;
the runner now defaults to that and retains wall-clock limits. This experiment's
original cap and score remain unchanged. New budgets need separate attempts.
Fresh contexts also discard unsaved analysis between visual iterations; this is
not a continuous multimodal agent session or a general comparison with other
harnesses/models.

## Harness issues retained

An initial preflight used a CLI flag Claux does not support; it made no model
request. A subsequent attempt could not connect because the isolated filesystem
omitted the actual CA-bundle directory behind the system certificate symlink.
That attempt produced no model output or tool calls and is recorded separately
as unavailable. TLS preflight was added before the evaluated attempt.

The original runner stopped on iteration one's nonzero round-limit exit. We
continued only the second iteration already included in the plan, using the
same model, images, budgets, and public feedback. Its completed artifact was
retained. A missing import in that continuation helper then interrupted optional
preview collection. The intact final files were independently collected and
graded without any additional model call. Raw original summaries and logs were
preserved; these issues were not silently erased or counted as model successes.

Raw transcripts, frozen inputs, launch/continuation scripts, and full grader
logs remain gitignored under the directories named in `result-summary.json`.
They are not committed because they contain private model reasoning. Public
artifacts contain no credentials. The task implementation and functional control
results are in `hyprland-visual/`; this report adds no hard-difficulty claim.

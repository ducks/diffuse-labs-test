# Hyprland / Claux vision pilot 002

Fresh attempt using the same Claux binary and OpenRouter model as pilot 001,
`deepseek/deepseek-v4-flash-vision-exp`. The task source commit at launch was
`ab49afc`. The actual saved config and launch plan both specify **200 model
rounds per invocation**, two visual iterations, and 180 seconds per iteration.
Private grading ran once after both iterations. There was no manual continuation
or model retry in this attempt.

**Evaluated failure:** both iterations reached the wall-clock limit after
180.1 seconds. Their checkpoints recorded 13 and 22 model rounds and 17 and 28
tool calls. Neither reached the 200-round cap. All six configuration files were
unchanged. The working starter passed functional checks and cold-boot capture
checks, then failed the visual comparison.

The trace shows repeated pixel-color, geometry, corner, and font measurements
using Python. No Write/Edit tool or shell config-writing command was attempted.
The six files were writable. One analysis command in iteration one encountered
a Python TypeError; there were no denied writes. The second fresh context
repeated substantial inspection rather than carrying over unsaved analysis.
These observations support an analysis-loop explanation, not certainty about
the model's internal decision process.

Checkpoint provider-reported costs sum to **$0.06339921736**. That is incomplete:
an in-flight request interrupted at timeout may have charges not present in the
last checkpoint. It is not an invoice or an exact total. No further model calls
were made after the two planned iterations.

## Interpretation

Removing the restrictive round cap did not produce an edit within this time
budget. That does not establish that the desktop task is hard or bad. This
attempt did not exercise a candidate configuration repair. The short wall-clock
budget and fresh-context screenshot loop remain important limitations. The
result should not be pooled with the differently budgeted first pilot into a
solve-rate or cross-model claim.

The task's functional controls are separate: two valid layouts pass and five
broken configurations fail in the intended phases. They demonstrate useful
grading behavior, not model difficulty.

## Evidence

`plan.json` and `launch-metadata.json` preserve the allowance, launch command,
source commit, task hashes, and binary hash. `result-summary.json` retains
checkpoint usage, timings, artifact hashes, final file hashes, and visual
errors. `submission/` contains the exact final six files; `verifier.txt` is a
compact phase record.

Raw transcripts, frozen source, the exact runner, public previews, and the full
verifier log remain gitignored under the raw directory named in the summary.
Only public material was visible in the Bubblewrap editing sandbox; the host
home, Nix store, reference config, and private tests were absent. Private model
reasoning and credentials are not included in these committed artifacts.

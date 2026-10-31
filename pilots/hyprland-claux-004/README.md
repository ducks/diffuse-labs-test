# Hyprland / Claux vision pilot 004

Fresh attempt using the revised prompt from commit `78815b1`. It explicitly
names the Hyprland 0.56.2 desktop and the Hyprland/Waybar/Foot/Wofi configuration,
and asks for a saved working draft before refinement. `prompt.json` retains the
exact text, including whitespace; the raw run also retains `prompt-1.txt`.

Settings otherwise match pilot 003: the same Claux binary and requested
OpenRouter model, `deepseek/deepseek-v4-flash-vision-exp`, one uninterrupted
context, 600 seconds, and a 200-model-round allowance. Six initial screenshots
were attached. There was no live preview feedback inside the editing context,
private grader feedback, manual continuation, or additional model retry.

**Evaluated failure:** the attempt reached its wall-clock limit at 600.1 seconds.
The final checkpoint recorded 31 model rounds and 44 tool-call entries. All six
submitted configuration files were unchanged. The post-attempt public preview
therefore reused the starter's cached capture result. Private grading ran after
the attempt: functional/cold-boot checks passed, but visual matching failed.

This is the same observed outcome with the clearer prompt in one fresh trial.
It does not establish that the task is hard, that prompt wording cannot help,
or that another model or a live visual-feedback harness would behave similarly.

`result-summary.json` retains checkpoint usage and cost. Cost is incomplete
because an interrupted in-flight request may not appear in the last checkpoint.
`plan.json` and `launch-metadata.json` retain settings and source/binary hashes.
`submission/` contains the exact six final files and `verifier.txt` the phase
summary. Full private transcripts, frozen inputs, runner, preview and verifier
logs remain gitignored under the raw directory named in the summary. No further
model calls were made for this pilot.

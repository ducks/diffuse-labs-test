# Hyprland / Claux vision pilot 003

A fresh attempt with one uninterrupted Claux context, a **600-second** wall-clock
limit and a **200-model-round** allowance. It used the same requested OpenRouter
model, `deepseek/deepseek-v4-flash-vision-exp`, and the same Claux binary as pilot
002. Six initial images were attached: target and current empty, tiled, and
launcher scenes. The exact task prompt is retained in `prompt.txt`.

**Evaluated failure:** the attempt timed out at 600.1 seconds. Its last checkpoint
recorded 34 model rounds and 43 tool-call entries. All six submitted configuration
files remained unchanged. Private grading ran afterward: the working starter
passed functional/cold-boot checks and failed the visual comparison. There was
no context reset, manual continuation, additional model retry, or private feedback.

More uninterrupted time did not produce an edit under these settings. The trace
shows source inspection and screenshot analysis; it confirms the model read
`instruction.md`, which explicitly names Hyprland and its configuration contract.
This does not establish general task difficulty or prove which prompt/model/
harness choice caused the behavior.

## Important limitations

This runner cannot provide screenshots during a Claux one-shot. It rendered
the initial desktop before launch and rendered the saved configuration after
completion. Thus this run tests longer uninterrupted editing with initial
images, not live visual iteration. It does not settle whether intermediate
rendering feedback would improve performance.

The outer prompt opened with a reference to `instruction.md` rather than naming
Hyprland directly. After this run, the user requested a clearer opening naming
Hyprland, Waybar, Foot, and Wofi and asking for a working first draft before
refinement. That change applies to future runs. This experiment's actual prompt,
inputs, budgets, and score are preserved unchanged.

The checkpoint reports $0.177105712 of provider cost. That is incomplete: an
interrupted in-flight request may have charges absent from the last checkpoint.
It is not an exact total or an invoice.

`plan.json`, `launch-metadata.json`, and `result-summary.json` retain settings,
source/binary hashes, usage, timing, submitted file hashes, and visual errors.
`submission/` is the exact final configuration. Raw model reasoning, images in
transcripts, the frozen task, runner, and complete grader log remain gitignored
in the raw directory named in the summary; credentials are not committed.

# Validation

The reference desktop uses pinned Nixpkgs and Hyprland 0.56.2, DejaVu fonts,
software rendering, a 1280×720 display at scale 1, and a 2 GiB/two-core QEMU VM.
Target images are produced by the real desktop and reviewed visually.

The final target-generation run produced zero normalized RGB pixel error across
boots for empty, tiled, and launcher scenes. An independent reference grading
run also passed all functional and visual checks. `validation.json` retains the
control results and source hashes; full local logs are under
`logs/hyprland-visual/`.

Both the reference dwindle layout and an alternate master layout pass. Negative
controls cover the working but incorrectly themed starting desktop, wrong
palette, wrong active border, missing terminal shortcut, and missing launcher
shortcut. All five fail in the expected semantic phase. Build or evaluation
errors do not count as successful negative controls.

Functional grading sends virtual keyboard events to the actual desktop. It
selects an application through Wofi, closes and opens windows through shortcuts,
types a random command into a Foot shell, verifies its user-owned file outside
the terminal, and switches workspace without moving existing windows. After a
cold boot, the three original visual scenes must recur within a 0.001 normalized
RGB MAE tolerance. Every target region must independently be within 0.012 MAE.

## Development findings

The first smoke test needed to wait for the compositor's control socket, rather
than treating the Wayland socket as sufficient readiness. Waybar's visible
layer is used instead of assuming a wrapped executable's process name.
Hyprland control commands use the pinned version's Lua API.

Foot's deprecated color-section syntax visibly polluted an early target; it
was corrected before installing the final targets. A launcher could register a
layer before painting, allowing an otherwise stable-frame check to capture the
desktop underneath. Waiting for actual visual change fixed this observed race.
Typing an application name before selecting it removes dependence on an initial
menu-selection state. These are harness fixes, not model failures.

Target-generation mode retains diagnostic captures even if repeatability fails;
inspect its result JSON before installing targets. Normal grading always enforces
the repeatability and target thresholds. Successful Nix derivations can be cached;
cache reuse must not be counted as another independent trial.

## Limits

The score is calibrated to this fixed renderer and the listed controls. It does
not establish semantic equivalence, adversarial security, cross-platform
perceptual quality, or difficulty across models. Independent regions and typed
shell checks reduce obvious screenshot shortcuts; they do not prove resistance
to every possible overlay or simulated desktop. There is no model judge in the
grader, no imported third-party screenshot dataset, and no Harbor integration.

Claux vision pilot records are separate from the functional controls. A model
attempt must see only the exported public workspace; model claims alone never
determine its score.

The [first exploratory Claux pilot](../pilots/hyprland-claux-001/README.md)
exhausted an explicitly configured 12-model-round limit in both visual
iterations, saved no edits, and failed visual grading. Its restrictive budget
and fresh-context iteration design prevent a difficulty conclusion. The runner's
future default was restored to Claux's normal 200 rounds with wall-clock limits;
the original trial's score and recorded settings are unchanged.

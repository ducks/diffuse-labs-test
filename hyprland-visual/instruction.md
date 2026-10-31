# Recreate a working Hyprland desktop from screenshots

The three images in `targets/` show an empty desktop, two tiled terminals, and
the application launcher. Recreate their appearance by editing `config/`.
The result must remain a working desktop, including after a cold boot.

The evaluator supplies a fixed NixOS machine with Hyprland 0.56.2, Waybar, Foot,
Wofi, DejaVu fonts, software rendering, one 1280×720 display at scale 1, and user
`desktop`. Hyprland reads `config/hypr/hyprland.lua`. The other files configure
Waybar, Foot, and Wofi. Only the six supplied config files are submitted; do not
change the VM, capture helpers, targets, or system packages. Do not implement a
mock compositor, draw a fake desktop, or use a target screenshot as wallpaper.

## Functional requirements

- Start Hyprland and one Waybar automatically, with no configuration errors.
- Super+Enter opens `desktop-terminal`, a real Foot shell.
- Super+Space opens `desktop-launcher`; selecting Terminal opens a real shell.
- Super+Q closes the focused window.
- Super+1, Super+2, and Super+3 switch to the corresponding workspaces.
- Keep the renderer at 1280×720, scale 1. Use DejaVu fonts. Disable animations
  and blinking cursors so completed renders can be compared consistently.
- Start with no application windows. The capture controller opens the supplied
  `desktop-card Workspace` and `desktop-card Notes` fixture windows in order.
  It then opens the launcher with the keyboard shortcut. The fixture programs
  and menu entries are fixed; configure their appearance, not their contents.
- All of this must work again after a complete shutdown and boot, without any
  commands being manually repeated in the guest.

## Visual checks

The grader captures all three scenes, before and after reboot. It compares the
bar, background, each terminal half and top edge, and the launcher region separately, using
normalized RGB mean absolute error. Every region must be at most 0.012 from its
target. Background agreement cannot compensate for a wrong bar or menu. A tiny
32×32 pointer area in the bottom-right corner is excluded. This is a fixed
renderer reproduction task, not a general perceptual-similarity benchmark.

Boot-to-boot captures must also agree within 0.001 normalized RGB mean absolute
error over the frame. Captures wait for stable rendering instead of taking the
first frame after a fixed delay. Functional checks are independent of images.

## Public preview

On the Linux/KVM host provided by a runner:

```sh
nix-build preview.nix --no-out-link --max-jobs 1 --cores 2
```

The result contains `captures/empty.png`, `captures/tiled.png`, and
`captures/launcher.png`. `vm.nix -A driverInteractive` provides a development
VM with the NixOS Python test driver's interactive console. Host builds can
download pinned dependencies; the desktop VM has no internet route.

Your starting configuration works but has the wrong theme and layout. You may
change all six config files. Runtime instance IDs, PIDs, and random keyboard
test inputs are not fixed and must not be hardcoded.

# Target provenance

Community inspiration was surveyed through the official Hyprland showcase:

https://hypr.land/hall_of_fame/

Examples reviewed include:

https://github.com/FlafyDev/hyprland_moon_rice_public

https://github.com/end-4/dots-hyprland

These are inspiration links, not imported tasks. This prototype does not bundle
their screenshots, wallpaper, dotfiles, or other assets. Its target is an
original Gruvbox layout rendered by the pinned VM from this repository's
reference configuration. It makes no claim to reproduce either community setup.
The solid background avoids dominant wallpaper pixels obscuring interface work.

Configuration API behavior was checked against the pinned upstream example:

https://github.com/hyprwm/Hyprland/blob/v0.56.2/example/hyprland.lua

Software-rendered VM feasibility was checked in a real NixOS/QEMU boot. The
fixed-renderer target must be regenerated and revalidated when packages, fonts,
display geometry, or fixture content change. Old and new versions must not be
combined into one solve-rate cohort.

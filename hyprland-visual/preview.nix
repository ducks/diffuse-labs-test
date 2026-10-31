{ configDir ? ./config }:
let pkgs = import (import ./nixpkgs.nix) {};
in pkgs.testers.runNixOSTest {
  name = "hyprland-visual-preview";
  enableOCR = false;
  skipTypeCheck = true;
  skipLint = true;
  extraPythonPackages = ps: [ ps.pillow ];
  globalTimeout = 180;
  nodes.desktop = import ./base.nix { inherit configDir; };
  testScript = builtins.readFile ./capture.py + ''
    desktop.start()
    ready()
    scene()
    print("HYPRLAND_PUBLIC_PREVIEW_CAPTURED")
  '';
}

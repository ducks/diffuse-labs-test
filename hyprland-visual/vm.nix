{ configDir ? ./config }:
let pkgs = import (import ./nixpkgs.nix) {};
in pkgs.testers.runNixOSTest {
  name = "hyprland-visual-development";
  enableOCR = false;
  skipTypeCheck = true;
  skipLint = true;
  nodes.desktop = import ./base.nix { inherit configDir; };
  testScript = ''
    desktop.start()
    desktop.wait_for_unit("multi-user.target")
  '';
}

{ configDir ? ./config, makeTargets ? false }:
let pkgs = import (import ./nixpkgs.nix) {};
in pkgs.testers.runNixOSTest {
  name = "hyprland-visual";
  enableOCR = false;
  skipTypeCheck = true;
  skipLint = true;
  extraPythonPackages = ps: [ ps.pillow ];
  globalTimeout = 480;
  nodes.desktop = import ./base.nix { inherit configDir; };
  testScript = ''
    MAKE_TARGETS = ${if makeTargets then "True" else "False"}
    TARGETS = __import__('pathlib').Path('${./targets}')
  '' + builtins.readFile ./capture.py + builtins.readFile ./tests/verify.py;
}

{ deploymentDir ? ./deployment, runName ? "terraform-k8s-docmill-spike" }:
let
  tools = import ./toolchain.nix;
  images = import ./images.nix;
in tools.pkgs.testers.runNixOSTest {
  name = runName;
  enableOCR = false;
  skipTypeCheck = true;
  skipLint = true;
  globalTimeout = 1500;
  nodes.cluster = {
    imports = [ (import ./base.nix { images = builtins.attrValues images; }) ];
    environment.etc."task-deployment".source = builtins.path {
      path = deploymentDir;
      name = "submitted-terraform";
    };
  };
  testScript = builtins.readFile ./tests/verify.py;
}

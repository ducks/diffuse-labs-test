{ deploymentDir ? ./deployment }:
let
  tools = import ./toolchain.nix;
  images = import ./images.nix;
in tools.pkgs.testers.runNixOSTest {
  name = "terraform-k8s-development";
  enableOCR = false;
  skipTypeCheck = true;
  skipLint = true;
  nodes.cluster = {
    imports = [ (import ./base.nix { images = builtins.attrValues images; }) ];
    environment.etc."task-deployment".source = deploymentDir;
  };
  testScript = ''
    cluster.start()
    cluster.wait_for_unit("k3s.service")
    cluster.wait_until_succeeds("kubectl get nodes --no-headers | grep -w Ready", timeout=240)
  '';
}

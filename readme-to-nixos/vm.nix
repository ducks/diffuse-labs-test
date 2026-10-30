# Public development VM: no hidden assertions or reference configuration.
{ moduleFile ? ./deployment.nix }:
let
  pkgs = import (import ./nixpkgs.nix) { config = {}; overlays = []; };
in pkgs.testers.runNixOSTest {
  name = "docmill-development-vm";
  enableOCR = false;
  skipTypeCheck = true;
  skipLint = true;
  nodes.dev = { lib, ... }: {
    imports = [ (builtins.toPath moduleFile) ];
    _module.args.appSource = import ./source.nix { inherit (pkgs) lib; };
    networking.useDHCP = lib.mkForce false;
    networking.interfaces.eth0.useDHCP = lib.mkForce false;
    environment.systemPackages = [ pkgs.python3 pkgs.curl pkgs.redis pkgs.util-linux ];
    virtualisation = { memorySize = 1024; cores = 1; diskSize = 2048; restrictNetwork = lib.mkForce true; };
    system.stateVersion = "25.11";
  };
  testScript = ''
    dev.start()
    dev.wait_for_unit("multi-user.target")
  '';
}

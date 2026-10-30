{ moduleFile ? ./deployment.nix }:
let
  pkgs = import (import ./nixpkgs.nix) { config = {}; overlays = []; };
  submitted = builtins.toPath moduleFile;
  node = { lib, ... }: {
    imports = [ submitted ];
    _module.args.appSource = import ./source.nix { inherit (pkgs) lib; };
    networking.useDHCP = lib.mkForce false;
    networking.interfaces.eth0.useDHCP = lib.mkForce false;
    environment.systemPackages = [ pkgs.python3 pkgs.curl pkgs.redis pkgs.util-linux ];
    virtualisation = { memorySize = 1024; cores = 1; diskSize = 2048; restrictNetwork = lib.mkForce true; };
    system.stateVersion = "25.11";
  };
in pkgs.testers.runNixOSTest {
  name = "readme-to-nixos-docmill";
  enableOCR = false;
  # The script receives dynamically generated machine objects from NixOS.
  skipTypeCheck = true;
  skipLint = true;
  globalTimeout = 900;
  nodes.alpha = node;
  nodes.beta = node;
  testScript = builtins.readFile ./tests/verify.py;
}

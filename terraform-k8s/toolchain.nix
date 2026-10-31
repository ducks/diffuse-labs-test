let
  pkgs = import (import ./nixpkgs.nix) { config.allowUnfree = true; };
in {
  inherit pkgs;
  terraform = pkgs.terraform.withPlugins (p: [ p.hashicorp_kubernetes ]);
}

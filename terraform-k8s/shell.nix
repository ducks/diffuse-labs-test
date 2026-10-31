let tools = import ./toolchain.nix;
in tools.pkgs.mkShell {
  packages = [ tools.terraform tools.pkgs.kubectl tools.pkgs.python3 ];
}

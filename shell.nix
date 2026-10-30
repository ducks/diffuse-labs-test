{ pkgs ? import (builtins.fetchTarball {
    url = "https://github.com/NixOS/nixpkgs/archive/9fbb54b33e91ee4ca368e35a78e0613c720600b3.tar.gz";
    sha256 = "sha256-cV5xEJJK3BvhU8rEd4mC9UsmDi5qscv/kzGPhBRC5WA=";
  }) {} }:
pkgs.mkShell {
  packages = [ pkgs.python3 pkgs.git pkgs.uv pkgs.docker-client pkgs.nix ];
  UV_PYTHON_DOWNLOADS = "never";
  UV_PYTHON = "${pkgs.python3}/bin/python3";
  # Avoid host Docker plugins overriding the matching Nix-provided versions.
  shellHook = ''
    export DOCKER_CONFIG="${toString ./.}/.docker"
    mkdir -p "$DOCKER_CONFIG"
    install -m 600 ${pkgs.writeText "docker-config.json" (builtins.toJSON {
      cliPluginsExtraDirs = [
        "${pkgs.docker-buildx}/libexec/docker/cli-plugins"
        "${pkgs.docker-compose}/libexec/docker/cli-plugins"
      ];
    })} "$DOCKER_CONFIG/config.json"
  '';
}

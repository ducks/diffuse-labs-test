{ pkgs ? import (import ./nixpkgs.nix) {} }:
pkgs.mkShell {
  packages = [
    (pkgs.python3.withPackages (ps: [ ps.psycopg ps.redis ]))
    pkgs.postgresql
    pkgs.redis
    pkgs.graphviz
  ];
}

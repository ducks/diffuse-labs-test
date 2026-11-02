{ workspace }:
let
  source = import (workspace + "/nixpkgs.nix");
  pkgs = import source {};
  development = import (workspace + "/vm.nix") {};
  tools = import (workspace + "/toolchain.nix");
  python = pkgs.python3.withPackages (ps: [ ps.psycopg ps.redis ]);
  layout = pkgs.runCommand "docmill-pilot-layout" {} ''
    mkdir -p $out/etc/nix $out/root $out/workspace $out/opt $out/tmp $out/usr/bin
    chmod 1777 $out/tmp
    printf 'root:x:0:0:root:/root:/bin/bash\n' > $out/etc/passwd
    printf 'root:x:0:\n' > $out/etc/group
    printf 'build-users-group =\nsandbox = false\nexperimental-features = nix-command\n' > $out/etc/nix/nix.conf
    ln -s ${source} $out/opt/nixpkgs
    ln -s ${development.driverInteractive} $out/opt/public-development-driver
    ln -s ${python} $out/opt/python
    ln -s ${pkgs.postgresql} $out/opt/postgresql
    ln -s ${pkgs.redis} $out/opt/redis
    ln -s ${pkgs.graphviz} $out/opt/graphviz
    ln -s ${pkgs.cacert}/etc/ssl $out/etc/ssl
    ln -s /bin/env $out/usr/bin/env
  '';
in pkgs.dockerTools.buildImageWithNixDb {
  name = "diffuse-terraform-pilot";
  tag = "001";
  compressor = "none";
  copyToRoot = pkgs.buildEnv {
    name = "docmill-pilot-root";
    pathsToLink = [ "/bin" "/etc" "/root" "/workspace" "/opt" "/tmp" "/usr" ];
    paths = [ layout pkgs.nix pkgs.bashInteractive pkgs.coreutils pkgs.git
      tools.terraform pkgs.kubectl pkgs.curl pkgs.python3 pkgs.ripgrep pkgs.findutils pkgs.gnugrep
      pkgs.gnused pkgs.gnutar pkgs.gzip pkgs.procps pkgs.which ];
  };
  config = {
    WorkingDir = "/workspace";
    Env = [ "PATH=/bin" "HOME=/root" "USER=root" "NIX_REMOTE=local"
      "NIX_PATH=nixpkgs=/opt/nixpkgs" "NIX_SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt"
      "SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt" "TERM=xterm" ];
    Cmd = [ "/bin/bash" ];
  };
}

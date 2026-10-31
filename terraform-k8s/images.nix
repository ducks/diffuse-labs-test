let
  tools = import ./toolchain.nix;
  inherit (tools) pkgs;
  python = pkgs.python3.withPackages (ps: [ ps.psycopg ps.redis ]);
  account = pkgs.runCommand "docmill-container-account" {} ''
    mkdir -p $out/etc $out/tmp
    chmod 1777 $out/tmp
    printf 'docmill:x:1000:1000:Docmill:/tmp:/bin/sh\n' > $out/etc/passwd
    printf 'docmill:x:1000:\n' > $out/etc/group
  '';
  renderer = pkgs.writeShellScriptBin "dot" ''
    # Public fault-injection barrier. The controller waits for an explicit
    # acknowledgement before killing the worker; no sleep chooses the fault.
    if [ -f "$DOCMILL_STORAGE/.render-pause" ]; then
      printf '%s\n' "$HOSTNAME" > "$DOCMILL_STORAGE/.render-entered"
      while [ -f "$DOCMILL_STORAGE/.render-pause" ]; do sleep 0.1; done
    fi
    exec ${pkgs.graphviz}/bin/dot "$@"
  '';
  app = pkgs.runCommand "docmill-container-source" {} ''
    mkdir -p $out/app
    cp -r ${./repository/docmill} $out/app/docmill
  '';
  postgres = pkgs.writeShellScriptBin "postgres-entrypoint" ''
    set -eu
    if [ ! -f "$PGDATA/PG_VERSION" ]; then
      ${pkgs.postgresql_17}/bin/initdb -D "$PGDATA" --locale=C --encoding=UTF8 --username=docmill --auth-local=trust --auth-host=scram-sha-256 --pwfile="$POSTGRES_PASSWORD_FILE"
      printf 'host all all 0.0.0.0/0 scram-sha-256\n' >> "$PGDATA/pg_hba.conf"
      ${pkgs.postgresql_17}/bin/pg_ctl -D "$PGDATA" -o '-c listen_addresses= -k /tmp' -w start
      ${pkgs.postgresql_17}/bin/createdb -h /tmp -U docmill docmill
      ${pkgs.postgresql_17}/bin/pg_ctl -D "$PGDATA" -m fast -w stop
    fi
    exec ${pkgs.postgresql_17}/bin/postgres -D "$PGDATA" -c listen_addresses='*' -k /tmp
  '';
  image = name: packages: command: env: pkgs.dockerTools.buildImage {
    inherit name;
    tag = "spike";
    copyToRoot = pkgs.buildEnv {
      name = name + "-root";
      paths = [ account pkgs.bash pkgs.coreutils ] ++ packages;
      pathsToLink = [ "/bin" "/etc" "/tmp" "/app" ];
    };
    config = {
      User = "1000:1000";
      Cmd = command;
      Env = [ "PATH=/bin" "HOME=/tmp" "LANG=C.UTF-8" ] ++ env;
    };
  };
in {
  app = image "docmill-app" [ python renderer app ] [ "python" "-m" "docmill" "api" ]
    [ "PYTHONPATH=/app" "PYTHONDONTWRITEBYTECODE=1" ];
  database = image "docmill-postgres" [ pkgs.postgresql_17 postgres ] [ "postgres-entrypoint" ]
    [ "PGDATA=/data/pgdata" "POSTGRES_PASSWORD_FILE=/run/credentials/db-password" ];
  cache = image "docmill-redis" [ pkgs.redis ]
    [ "redis-server" "--bind" "0.0.0.0" "--save" "" "--appendonly" "no" "--protected-mode" "no" ] [];
}

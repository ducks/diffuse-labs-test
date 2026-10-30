{ pkgs, appSource, ... }:
let
  python = pkgs.python3.withPackages (ps: [ ps.psycopg ps.redis ]);
  common = {
    DATABASE_URL = "postgresql:///docmill?host=/run/postgresql";
    REDIS_URL = "redis://127.0.0.1:6379/0";
    DOCMILL_STORAGE = "/var/lib/docmill/reports";
    DOCMILL_TOKEN_FILE = "/run/secrets/docmill-api";
    DOCMILL_BIND = "0.0.0.0";
    DOCMILL_PORT = "8080";
    PYTHONPATH = "${appSource}";
  };
  role = mode: {
    wantedBy = [ "multi-user.target" ];
    wants = [ "postgresql.service" "redis-docmill.service" ];
    after = [ "postgresql.service" "redis-docmill.service" "docmill-migrate.service" ];
    requires = [ "docmill-migrate.service" ];
    environment = common;
    path = [ pkgs.graphviz ];
    unitConfig.StartLimitIntervalSec = 0;
    serviceConfig = {
      User = "docmill";
      Group = "docmill";
      ExecStart = "${python}/bin/python -m docmill ${mode}";
      Restart = "always";
      RestartSec = 1;
      UMask = "0027";
      NoNewPrivileges = true;
      PrivateTmp = true;
    };
  };
in {
  users.groups.docmill = {};
  users.users.docmill = { isSystemUser = true; group = "docmill"; };
  services.postgresql = {
    enable = true;
    ensureDatabases = [ "docmill" ];
    ensureUsers = [ { name = "docmill"; ensureDBOwnership = true; } ];
  };
  services.redis.servers.docmill = { enable = true; port = 6379; bind = "127.0.0.1"; };
  systemd.tmpfiles.rules = [
    "d /var/lib/docmill 0750 docmill docmill -"
    "d /var/lib/docmill/reports 0750 docmill docmill -"
  ];
  systemd.services.docmill-migrate = {
    wantedBy = [ "multi-user.target" ];
    wants = [ "postgresql.service" ];
    after = [ "postgresql.service" ];
    before = [ "docmill-api.service" "docmill-worker.service" ];
    environment = common;
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      User = "docmill";
      Group = "docmill";
      ExecStart = "${python}/bin/python -m docmill migrate";
    };
  };
  systemd.services.docmill-api = role "api";
  systemd.services.docmill-worker = role "worker";
  networking.firewall.allowedTCPPorts = [ 8080 ];
}

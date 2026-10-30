{ config, lib, pkgs, appSource, ... }:
let
  python = pkgs.python3.withPackages (ps: [ ps.psycopg ps.redis ]);
  common = {
    wantedBy = [ "multi-user.target" ];
    wants = [ "postgresql.service" "redis-docmill.service" ];
    after = [ "postgresql.service" "redis-docmill.service" ];
    path = [ pkgs.graphviz ];
    environment = {
      PYTHONPATH = "${appSource}";
      PYTHONUNBUFFERED = "1";
      DATABASE_URL = "postgresql:///docmill?host=/run/postgresql";
      REDIS_URL = "redis://127.0.0.1:6379/0";
      DOCMILL_STORAGE = "/var/lib/docmill/reports";
      DOCMILL_TOKEN_FILE = "/run/secrets/docmill-api";
      DOCMILL_BIND = "0.0.0.0";
      DOCMILL_PORT = "8080";
    };
    unitConfig.StartLimitIntervalSec = 0;
    serviceConfig = {
      User = "docmill";
      Group = "docmill";
      StateDirectory = "docmill";
      StateDirectoryMode = "0700";
      UMask = "0077";
      # Serialize the two roles when initializing a clean database.
      ExecStartPre = "${pkgs.util-linux}/bin/flock /var/lib/docmill/migrate.lock ${python}/bin/python -m docmill migrate";
      Restart = "on-failure";
      RestartSec = "2s";
      NoNewPrivileges = true;
      PrivateTmp = true;
      ProtectSystem = "strict";
      ProtectHome = true;
    };
  };
in {
  users.groups.docmill = {};
  users.users.docmill = {
    isSystemUser = true;
    group = "docmill";
    home = "/var/lib/docmill";
  };

  networking.firewall.allowedTCPPorts = [ 8080 ];

  services.postgresql = {
    enable = true;
    enableTCPIP = false;
    ensureDatabases = [ "docmill" ];
    ensureUsers = [{ name = "docmill"; ensureDBOwnership = true; }];
  };
  services.redis.servers.docmill = {
    enable = true;
    bind = "127.0.0.1";
    port = 6379;
  };

  systemd.tmpfiles.rules = [
    "d /var/lib/docmill 0700 docmill docmill -"
    "d /var/lib/docmill/reports 0700 docmill docmill -"
  ];

  systemd.services.docmill-api = lib.recursiveUpdate common {
    description = "Docmill HTTP API";
    serviceConfig.ExecStart = "${python}/bin/python -m docmill api";
  };
  systemd.services.docmill-worker = lib.recursiveUpdate common {
    description = "Docmill report worker";
    serviceConfig.ExecStart = "${python}/bin/python -m docmill worker";
  };
}

locals {
  ns  = var.namespace
  sec = var.credential_secret_name
  app_env = {
    DATABASE_URL       = "postgresql://docmill@postgres:5432/docmill"
    REDIS_URL          = "redis://redis:6379/0"
    DOCMILL_STORAGE    = "/reports"
    DOCMILL_TOKEN_FILE = "/run/credentials/api-token"
    DOCMILL_BIND       = "0.0.0.0"
    DOCMILL_PORT       = "8080"
  }
}

resource "kubernetes_persistent_volume_claim_v1" "pg" {
  metadata {
    name      = "postgres-data"
    namespace = local.ns
  }
  wait_until_bound = false
  spec {
    access_modes = ["ReadWriteOnce"]
    resources { requests = { storage = "1Gi" } }
  }
}

resource "kubernetes_persistent_volume_claim_v1" "reports" {
  metadata {
    name      = "reports"
    namespace = local.ns
  }
  wait_until_bound = false
  spec {
    access_modes = ["ReadWriteOnce"]
    resources { requests = { storage = "1Gi" } }
  }
}

resource "kubernetes_deployment_v1" "postgres" {
  metadata {
    name      = "postgres"
    namespace = local.ns
    labels    = { app = "postgres" }
  }
  spec {
    replicas = 1
    strategy { type = "Recreate" }
    selector { match_labels = { app = "postgres" } }
    template {
      metadata { labels = { app = "postgres" } }
      spec {
        security_context {
          run_as_user     = 1000
          run_as_group    = 1000
          fs_group        = 1000
          run_as_non_root = true
        }
        container {
          name              = "postgres"
          image             = "docmill-postgres:spike"
          image_pull_policy = "Never"
          port { container_port = 5432 }
          volume_mount {
            name       = "data"
            mount_path = "/data"
          }
          volume_mount {
            name       = "cred"
            mount_path = "/run/credentials"
            read_only  = true
          }
          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
          readiness_probe {
            tcp_socket { port = 5432 }
            period_seconds = 3
          }
        }
        volume {
          name = "data"
          persistent_volume_claim { claim_name = kubernetes_persistent_volume_claim_v1.pg.metadata[0].name }
        }
        volume {
          name = "tmp"
          empty_dir {}
        }
        volume {
          name = "cred"
          secret {
            secret_name  = local.sec
            default_mode = "0440"
            items {
              key  = "db-password"
              path = "db-password"
            }
          }
        }
      }
    }
  }
  wait_for_rollout = false
}

resource "kubernetes_service_v1" "postgres" {
  metadata {
    name      = "postgres"
    namespace = local.ns
  }
  spec {
    type     = "ClusterIP"
    selector = { app = "postgres" }
    port {
      port        = 5432
      target_port = 5432
    }
  }
}

resource "kubernetes_deployment_v1" "redis" {
  metadata {
    name      = "redis"
    namespace = local.ns
    labels    = { app = "redis" }
  }
  spec {
    replicas = 1
    selector { match_labels = { app = "redis" } }
    template {
      metadata { labels = { app = "redis" } }
      spec {
        security_context {
          run_as_user     = 1000
          run_as_group    = 1000
          run_as_non_root = true
        }
        container {
          name              = "redis"
          image             = "docmill-redis:spike"
          image_pull_policy = "Never"
          working_dir       = "/tmp"
          port { container_port = 6379 }
          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
        }
        volume {
          name = "tmp"
          empty_dir {}
        }
      }
    }
  }
  wait_for_rollout = false
}

resource "kubernetes_service_v1" "redis" {
  metadata {
    name      = "redis"
    namespace = local.ns
  }
  spec {
    type     = "ClusterIP"
    selector = { app = "redis" }
    port {
      port        = 6379
      target_port = 6379
    }
  }
}

resource "kubernetes_deployment_v1" "app" {
  for_each = toset(["api", "worker"])
  metadata {
    name      = each.key
    namespace = local.ns
    labels    = { app = each.key }
  }
  spec {
    replicas = 1
    strategy { type = "Recreate" }
    selector { match_labels = { app = each.key } }
    template {
      metadata { labels = { app = each.key } }
      spec {
        security_context {
          run_as_user     = 1000
          run_as_group    = 1000
          fs_group        = 1000
          run_as_non_root = true
        }
        dynamic "init_container" {
          for_each = each.key == "api" ? [1] : []
          content {
            name              = "migrate"
            image             = "docmill-app:spike"
            image_pull_policy = "Never"
            command           = ["python", "-m", "docmill", "migrate"]
            dynamic "env" {
              for_each = local.app_env
              content {
                name  = env.key
                value = env.value
              }
            }
            env {
              name = "PGPASSWORD"
              value_from {
                secret_key_ref {
                  name = local.sec
                  key  = "db-password"
                }
              }
            }
            volume_mount {
              name       = "tmp"
              mount_path = "/tmp"
            }
          }
        }
        container {
          name              = each.key
          image             = "docmill-app:spike"
          image_pull_policy = "Never"
          command           = ["python", "-m", "docmill", each.key]
          dynamic "env" {
            for_each = local.app_env
            content {
              name  = env.key
              value = env.value
            }
          }
          env {
            name = "PGPASSWORD"
            value_from {
              secret_key_ref {
                name = local.sec
                key  = "db-password"
              }
            }
          }
          security_context {
            allow_privilege_escalation = false
          }
          dynamic "port" {
            for_each = each.key == "api" ? [1] : []
            content { container_port = 8080 }
          }
          dynamic "readiness_probe" {
            for_each = each.key == "api" ? [1] : []
            content {
              http_get {
                path = "/health"
                port = 8080
              }
              period_seconds = 3
            }
          }
          volume_mount {
            name       = "reports"
            mount_path = "/reports"
          }
          volume_mount {
            name       = "cred"
            mount_path = "/run/credentials"
            read_only  = true
          }
          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
        }
        volume {
          name = "reports"
          persistent_volume_claim { claim_name = kubernetes_persistent_volume_claim_v1.reports.metadata[0].name }
        }
        volume {
          name = "tmp"
          empty_dir {}
        }
        volume {
          name = "cred"
          secret {
            secret_name  = local.sec
            default_mode = "0440"
            items {
              key  = "api-token"
              path = "api-token"
            }
          }
        }
      }
    }
  }
  wait_for_rollout = false
}

resource "kubernetes_service_v1" "api" {
  metadata {
    name      = "api"
    namespace = local.ns
  }
  spec {
    type     = "NodePort"
    selector = { app = "api" }
    port {
      port        = 8080
      target_port = 8080
      node_port   = var.api_node_port
    }
  }
}

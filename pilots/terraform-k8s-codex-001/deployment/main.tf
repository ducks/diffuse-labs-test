locals {
  app_env = {
    DATABASE_URL       = "postgresql://docmill@postgres:5432/docmill"
    REDIS_URL          = "redis://redis:6379/0"
    DOCMILL_STORAGE    = "/reports"
    DOCMILL_TOKEN_FILE = "/run/credentials/api-token"
    DOCMILL_BIND       = "0.0.0.0"
    DOCMILL_PORT       = "8080"
  }
}

resource "kubernetes_persistent_volume_claim_v1" "data" {
  for_each = toset(["postgres", "reports"])
  metadata {
    name      = each.key
    namespace = var.namespace
  }
  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = "local-path"
    resources { requests = { storage = "1Gi" } }
  }
  wait_until_bound = false
}

resource "kubernetes_service_v1" "backend" {
  for_each = { postgres = 5432, redis = 6379 }
  metadata {
    name      = each.key
    namespace = var.namespace
  }
  spec {
    selector = { app = each.key }
    port {
      port        = each.value
      target_port = each.value
    }
  }
}

resource "kubernetes_deployment_v1" "backend" {
  for_each = { postgres = 5432, redis = 6379 }
  metadata {
    name      = each.key
    namespace = var.namespace
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
          run_as_user            = 1000
          run_as_group           = 1000
          run_as_non_root        = true
          fs_group               = 1000
          fs_group_change_policy = "OnRootMismatch"
        }
        container {
          name              = each.key
          image             = "docmill-${each.key}:spike"
          command           = each.key == "postgres" ? ["/bin/sh", "-c", "if [ -d \"$PGDATA\" ]; then chmod 700 \"$PGDATA\"; fi; exec postgres-entrypoint"] : null
          image_pull_policy = "Never"
          port { container_port = each.value }
          dynamic "volume_mount" {
            for_each = each.key == "postgres" ? [1] : []
            content {
              name       = "data"
              mount_path = "/data"
            }
          }
          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
          volume_mount {
            name       = "credentials"
            mount_path = "/run/credentials"
            read_only  = true
          }
          readiness_probe {
            tcp_socket { port = each.value }
            initial_delay_seconds = 2
            period_seconds        = 2
          }
        }
        dynamic "volume" {
          for_each = each.key == "postgres" ? [1] : []
          content {
            name = "data"
            persistent_volume_claim { claim_name = kubernetes_persistent_volume_claim_v1.data["postgres"].metadata[0].name }
          }
        }
        volume {
          name = "tmp"
          empty_dir {}
        }
        volume {
          name = "credentials"
          secret { secret_name = var.credential_secret_name }
        }
      }
    }
  }
}

resource "kubernetes_deployment_v1" "app" {
  for_each = toset(["api", "worker"])
  metadata {
    name      = each.key
    namespace = var.namespace
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
          run_as_user            = 1000
          run_as_group           = 1000
          run_as_non_root        = true
          fs_group               = 1000
          fs_group_change_policy = "OnRootMismatch"
        }
        init_container {
          name              = "migrate"
          image             = "docmill-app:spike"
          image_pull_policy = "Never"
          command           = ["/bin/sh", "-c", "until python -m docmill migrate; do sleep 2; done"]
          env {
            name  = "DATABASE_URL"
            value = local.app_env.DATABASE_URL
          }
          env {
            name = "PGPASSWORD"
            value_from {
              secret_key_ref {
                name = var.credential_secret_name
                key  = "db-password"
              }
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
                name = var.credential_secret_name
                key  = "db-password"
              }
            }
          }
          volume_mount {
            name       = "reports"
            mount_path = "/reports"
          }
          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
          volume_mount {
            name       = "credentials"
            mount_path = "/run/credentials"
            read_only  = true
          }
          dynamic "readiness_probe" {
            for_each = each.key == "api" ? [1] : []
            content {
              http_get {
                path = "/health"
                port = 8080
              }
              period_seconds = 2
            }
          }
        }
        volume {
          name = "reports"
          persistent_volume_claim { claim_name = kubernetes_persistent_volume_claim_v1.data["reports"].metadata[0].name }
        }
        volume {
          name = "tmp"
          empty_dir {}
        }
        volume {
          name = "credentials"
          secret { secret_name = var.credential_secret_name }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "api" {
  metadata {
    name      = "api"
    namespace = var.namespace
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

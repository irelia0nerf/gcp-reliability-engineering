terraform {
  required_version = ">= 1.9.0, < 2.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0, < 8.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  api_env = {
    ATLAS_PROJECT_ID               = var.project_id
    ATLAS_REGION                   = var.region
    ATLAS_QUEUE_NAME               = var.queue_name
    ATLAS_EXPECTED_AUDIENCE        = var.expected_audience
    ATLAS_CALLERS_JSON             = jsonencode(var.caller_tenant_map)
    ATLAS_TASK_SERVICE_ACCOUNT     = var.enable_infra ? google_service_account.task[0].email : ""
    ATLAS_DISPATCH_SERVICE_ACCOUNT = var.enable_infra ? google_service_account.dispatcher[0].email : ""
    ATLAS_BIND_HOST                = "0.0.0.0"
  }
}

# This entire directory is opt-in. CI never plans or applies cloud resources.
resource "google_service_account" "runtime" {
  count        = var.enable_infra ? 1 : 0
  account_id   = "atlas-runtime"
  display_name = "Atlas Regional Runtime"
}

resource "google_service_account" "task" {
  count        = var.enable_infra ? 1 : 0
  account_id   = "atlas-task-invoker"
  display_name = "Atlas Tasks OIDC Identity"
}

resource "google_service_account" "dispatcher" {
  count        = var.enable_infra ? 1 : 0
  account_id   = "atlas-dispatch-invoker"
  display_name = "Atlas Scheduler OIDC Identity"
}

resource "google_sql_database_instance" "postgres" {
  count               = var.enable_infra ? 1 : 0
  name                = "atlas-regional-db"
  region              = var.region
  database_version    = "POSTGRES_15"
  deletion_protection = true

  settings {
    tier              = "db-custom-2-7680"
    availability_type = "REGIONAL"
    disk_size         = 20
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = true
    }

    # Cloud SQL Auth Proxy socket on Cloud Run; no authorised public networks.
    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }
  }
}

resource "google_sql_database" "atlas" {
  count    = var.enable_infra ? 1 : 0
  name     = "atlas"
  instance = google_sql_database_instance.postgres[0].name
}

resource "google_cloud_tasks_queue" "queue" {
  count    = var.enable_infra ? 1 : 0
  name     = var.queue_name
  location = var.region

  rate_limits {
    max_dispatches_per_second = 2
    max_concurrent_dispatches = 5
  }
  retry_config {
    max_attempts  = 5
    min_backoff   = "10s"
    max_backoff   = "300s"
    max_doublings = 3
  }
}

resource "google_project_iam_member" "runtime_sql_client" {
  count   = var.enable_infra ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime[0].email}"
}

resource "google_project_iam_member" "runtime_tasks_enqueuer" {
  count   = var.enable_infra ? 1 : 0
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.runtime[0].email}"
}

resource "google_service_account_iam_member" "runtime_can_attach_task_identity" {
  count              = var.enable_infra ? 1 : 0
  service_account_id = google_service_account.task[0].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.runtime[0].email}"
}

resource "google_secret_manager_secret_iam_member" "runtime_db_dsn" {
  count     = var.enable_infra ? 1 : 0
  secret_id = var.database_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime[0].email}"
}

resource "google_cloud_run_v2_service" "api" {
  count               = var.enable_infra ? 1 : 0
  name                = "atlas-regional-api"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  deletion_protection = true
  custom_audiences    = [var.expected_audience]

  template {
    service_account                  = google_service_account.runtime[0].email
    max_instance_request_concurrency = 8
    timeout                          = "60s"
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      image = var.image_digest
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
      dynamic "env" {
        for_each = local.api_env
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name = "ATLAS_DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = var.database_secret_id
            version = "latest"
          }
        }
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres[0].connection_name]
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "task_invoker" {
  count    = var.enable_infra ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.task[0].email}"
}

resource "google_cloud_run_v2_service_iam_member" "dispatch_invoker" {
  count    = var.enable_infra ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.dispatcher[0].email}"
}

resource "google_cloud_run_v2_service_iam_member" "caller_invokers" {
  for_each = var.enable_infra ? toset(keys(var.caller_tenant_map)) : toset([])
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${each.key}"
}

# Paused even when provisioned; no dispatch until a separate explicit approval.
resource "google_cloud_scheduler_job" "outbox_tick" {
  count            = var.enable_infra ? 1 : 0
  name             = "atlas-outbox-dispatch"
  region           = var.region
  schedule         = "*/5 * * * *"
  time_zone        = "Etc/UTC"
  paused           = true
  attempt_deadline = "120s"

  http_target {
    uri         = "${google_cloud_run_v2_service.api[0].uri}/internal/dispatch"
    http_method = "POST"
    headers = {
      "Content-Type" = "application/json"
    }
    oidc_token {
      service_account_email = google_service_account.dispatcher[0].email
      audience              = var.expected_audience
    }
  }
}

output "cloud_run_url" {
  value = var.enable_infra ? google_cloud_run_v2_service.api[0].uri : null
}

output "deployment_status" {
  value = var.enable_infra ? "OPTED_IN_REQUIRES_APPROVAL" : "DISABLED_NO_RESOURCES"
}

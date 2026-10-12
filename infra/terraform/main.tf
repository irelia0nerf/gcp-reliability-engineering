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

# Illustrative scaffold only. Does NOT run the SQLite Atlas service.
# Disabled unless an operator explicitly opts into billed resources.
resource "google_cloud_run_v2_service" "placeholder" {
  count               = var.enable_service ? 1 : 0
  name                = "atlas-reliability-sandbox"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  deletion_protection = true

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      image = var.container_image
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }
}

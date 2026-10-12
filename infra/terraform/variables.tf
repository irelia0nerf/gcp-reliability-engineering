variable "project_id" {
  description = "Placeholder GCP project ID for offline validation only."
  type        = string
  default     = "example-reliability-lab-000"
}

variable "region" {
  description = "Regional example; no multi-region or failover."
  type        = string
  default     = "southamerica-east1"
}

variable "enable_service" {
  description = "Opt-in billing/deployment guard, false by default."
  type        = bool
  default     = false
}

variable "container_image" {
  description = "Illustrative image only. Actual deployment needs reviewed immutable image."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

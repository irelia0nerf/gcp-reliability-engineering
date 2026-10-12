variable "project_id" {
  description = "Dedicated, preapproved GCP project. Empty for CI validation."
  type        = string
  default     = ""
}
variable "region" {
  description = "Single region; no cross-region failover."
  type        = string
  default     = "southamerica-east1"
}
variable "enable_infra" {
  description = "Danger: incurs Google Cloud charges. Remain false until signed-off."
  type        = bool
  default     = false
}
variable "queue_name" {
  type    = string
  default = "atlas-regional-tasks"
}
variable "expected_audience" {
  description = "Stable custom Cloud Run audience, independent of generated service URL."
  type        = string
  default     = ""
  validation {
    condition     = !var.enable_infra || startswith(var.expected_audience, "https://")
    error_message = "Set a trusted HTTPS audience before enabling GCP."
  }
}
variable "image_digest" {
  description = "Explicit immutable OCI digest (never use :latest)."
  type        = string
  default     = ""
  validation {
    condition     = !var.enable_infra || can(regex("@sha256:[0-9a-f]{64}$", var.image_digest))
    error_message = "Provide an OCI image pinned to a sha256 digest."
  }
}
variable "database_secret_id" {
  description = "Preexisting Secret Manager secret containing PostgreSQL DSN; secret bytes NEVER passed to Terraform."
  type        = string
  default     = ""
  validation {
    condition     = !var.enable_infra || startswith(var.database_secret_id, "projects/")
    error_message = "Preprovision full Secret Manager resource ID."
  }
}
variable "caller_tenant_map" {
  description = "Allowlisted Google service account principals, tenant and scopes; no secrets."
  type = map(object({
    tenant = string
    scopes = list(string)
  }))
  default = {}
  validation {
    condition     = !var.enable_infra || length(var.caller_tenant_map) > 0
    error_message = "Declare at least one authenticated caller principal."
  }
}

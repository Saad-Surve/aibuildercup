variable "project_id" {
  description = "GCP project ID."
  type        = string
  default     = "habeas-codus"
}

variable "region" {
  description = "Single region for all services."
  type        = string
  default     = "us-central1"
}

variable "terraform_service_account" {
  description = "Service account Terraform impersonates."
  type        = string
  default     = "terraform@habeas-codus.iam.gserviceaccount.com"
}

variable "allowed_origins" {
  description = "Browser origins allowed to upload to the media bucket."
  type        = list(string)
  default = [
    "http://localhost:3000",
    "http://localhost:8080",
    "https://habeas-codus.web.app",
    "https://habeas-codus.firebaseapp.com",
  ]
}

variable "engineer_emails" {
  description = "Google account emails of the engineers (empty = skip IAM bindings)."
  type        = list(string)
  default = [
    "yusufsodawala7@gmail.com",
    "ankitmishra21022003@gmail.com",
  ]
}

variable "temp_retention_days" {
  description = "Lifecycle deletion for temporary media."
  type        = number
  default     = 7
}

variable "noncurrent_retention_days" {
  description = "Lifecycle deletion for noncurrent (archived) versions in versioned buckets. Backstop against version pile-up; never touches live objects."
  type        = number
  default     = 30
}

variable "billing_account_id" {
  description = "Billing account that owns the budget and kill switch."
  type        = string
  default     = "014B5B-1E8419-7A90A3"
}

variable "budget_currency" {
  description = "Billing account currency."
  type        = string
  default     = "INR"
}

variable "budget_amount" {
  description = "Budget threshold in the billing currency. 17000 INR is about 200 USD."
  type        = string
  default     = "17000"
}

variable "killswitch_dry_run" {
  description = "When true the kill switch logs only and does not disable billing."
  type        = bool
  default     = false
}

variable "github_repository" {
  description = "GitHub repository allowed to federate into the deployer service account."
  type        = string
  default     = "Saad-Surve/aibuildercup"
}

variable "api_url" {
  description = <<-EOT
    Public base URL of the API Cloud Run service. When set, the transcribe Pub/Sub
    subscription pushes GCS `object finalized` events to it (design diagrams 4/5). Leave blank
    locally; set it to the deployed service URL so the event path is the trigger of record.
  EOT
  type        = string
  default     = ""
}

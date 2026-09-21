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
  description = "Budget threshold in the billing currency. 8500 INR is about 100 USD."
  type        = string
  default     = "8500"
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

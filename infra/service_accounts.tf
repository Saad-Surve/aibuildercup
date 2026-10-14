locals {
  runtime_sas = {
    api        = "creator-studio-api"
    transcribe = "creator-studio-transcribe"
    deployer   = "creator-studio-deployer"
  }
}

resource "google_service_account" "runtime" {
  for_each = local.runtime_sas

  account_id   = each.value
  display_name = "Creator Studio ${each.key}"
  project      = var.project_id
}

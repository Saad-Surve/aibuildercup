locals {
  runtime_sas = {
    api          = "creator-studio-api"
    transcribe   = "creator-studio-transcribe"
    analysis     = "creator-studio-analysis"
    social_sync  = "creator-studio-social-sync"
    media        = "creator-studio-media"
    localization = "creator-studio-localization"
    deployer     = "creator-studio-deployer"
    web          = "creator-studio-web"
  }
}

resource "google_service_account" "runtime" {
  for_each = local.runtime_sas

  account_id   = each.value
  display_name = "Creator Studio ${each.key}"
  project      = var.project_id
}

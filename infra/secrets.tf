locals {
  secret_names = [
    "youtube-oauth-client-id",
    "youtube-oauth-client-secret",
    "meta-app-id",
    "meta-app-secret",
    "session-signing-secret",
  ]
}

resource "google_secret_manager_secret" "secrets" {
  for_each = toset(local.secret_names)

  secret_id = each.value
  project   = var.project_id

  replication {
    auto {}
  }
}

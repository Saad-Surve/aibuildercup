resource "google_kms_key_ring" "creator_studio" {
  name     = "creator-studio-keyring"
  project  = var.project_id
  location = var.region
}

resource "google_kms_crypto_key" "user_token_key" {
  name            = "user-token-key"
  key_ring        = google_kms_key_ring.creator_studio.id
  rotation_period = "7776000s" # 90 days
}

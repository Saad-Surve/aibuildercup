resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  project       = var.project_id
  repository_id = "creator-studio-containers"
  format        = "DOCKER"
  description   = "Container images for Creator Helper Studio."
}

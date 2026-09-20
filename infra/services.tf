resource "google_project_service" "required" {
  for_each = toset([
    "firestore.googleapis.com",
    "pubsub.googleapis.com",
    "bigquery.googleapis.com",
    "cloudkms.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudfunctions.googleapis.com",
    "eventarc.googleapis.com",
    "billingbudgets.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Firestore security rules.
#
# The backend uses the Admin SDK, which bypasses rules, so the client surface is locked down
# entirely. The rules file lives at the repo root so `firebase deploy --only firestore:rules`
# and Terraform deploy the exact same source.

resource "google_firebaserules_ruleset" "firestore" {
  project = var.project_id

  source {
    files {
      name    = "firestore.rules"
      content = file("${path.module}/../firestore.rules")
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_firebaserules_release" "firestore" {
  project      = var.project_id
  name         = "cloud.firestore"
  ruleset_name = google_firebaserules_ruleset.firestore.name
}

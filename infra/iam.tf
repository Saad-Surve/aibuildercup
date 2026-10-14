data "google_project" "current" {}

locals {
  sa_roles = {
    api = [
      "roles/datastore.user",
      "roles/storage.objectAdmin",
      "roles/pubsub.publisher",
      "roles/secretmanager.secretAccessor",
      "roles/aiplatform.user",
      "roles/cloudkms.cryptoKeyEncrypterDecrypter",
      # DELETE /api/me removes the Firebase Auth account via the Admin SDK.
      "roles/firebaseauth.admin",
      # Transcription runs inline in the API service (background task), so the API SA needs
      # Speech access until the worker moves to its own service.
      "roles/speech.client",
    ]
    transcribe = [
      "roles/storage.objectAdmin",
      "roles/datastore.user",
      "roles/pubsub.publisher",
      "roles/pubsub.subscriber",
      "roles/speech.client",
    ]
    deployer = [
      "roles/artifactregistry.writer",
      "roles/run.admin",
      "roles/iam.serviceAccountUser",
      "roles/firebasehosting.admin",
      # Cloud Run deploy attaches the OAuth secrets (youtube-oauth-client-*) and checks for a
      # `latest` version before attaching. secretAccessor reads the values; viewer reads the
      # version metadata (`versions.get`) that the existence check needs.
      "roles/secretmanager.secretAccessor",
      "roles/secretmanager.viewer",
    ]
  }
}

resource "google_project_iam_member" "sa_roles" {
  for_each = merge([
    for sa, roles in local.sa_roles : {
      for r in roles : "${sa}--${r}" => { sa = sa, role = r }
    }
  ]...)

  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.runtime[each.value.sa].email}"
}

# The API signs V4 upload/download URLs through the IAM signBlob API, so its runtime
# service account must be able to mint signatures for itself.
resource "google_service_account_iam_member" "api_sign_blob" {
  service_account_id = google_service_account.runtime["api"].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.runtime["api"].email}"
}

# Cloud Storage's service agent must be able to publish object notifications.
resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.topics["video_events"].name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"
}

# The Pub/Sub service agent mints the OIDC push token as the transcribe service account.
resource "google_service_account_iam_member" "pubsub_push_token_creator" {
  service_account_id = google_service_account.runtime["transcribe"].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Eventarc invokes the kill switch using the default compute service account.
resource "google_project_iam_member" "eventarc_compute_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}

# Engineers. Add emails to var.engineer_emails to activate these bindings.
locals {
  engineer_roles = [
    "roles/viewer",
    "roles/run.developer",
    "roles/artifactregistry.writer",
    "roles/logging.viewer",
    "roles/iam.serviceAccountUser",
  ]

  engineer_members = {
    for pair in setproduct(var.engineer_emails, local.engineer_roles) :
    "${pair[0]}--${pair[1]}" => { email = pair[0], role = pair[1] }
  }
}

resource "google_project_iam_member" "engineers" {
  for_each = local.engineer_members

  project = var.project_id
  role    = each.value.role
  member  = "user:${each.value.email}"
}

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
    ]
    transcribe = [
      "roles/storage.objectAdmin",
      "roles/datastore.user",
      "roles/pubsub.publisher",
      "roles/pubsub.subscriber",
      "roles/speech.client",
    ]
    analysis = [
      "roles/storage.objectViewer",
      "roles/datastore.user",
      "roles/aiplatform.user",
      "roles/pubsub.publisher",
      "roles/pubsub.subscriber",
    ]
    social_sync = [
      "roles/secretmanager.secretAccessor",
      "roles/cloudkms.cryptoKeyDecrypter",
      "roles/bigquery.dataEditor",
      "roles/storage.objectCreator",
      "roles/datastore.viewer",
      "roles/pubsub.subscriber",
    ]
    media = [
      "roles/storage.objectAdmin",
      "roles/datastore.user",
      "roles/pubsub.publisher",
      "roles/pubsub.subscriber",
    ]
    localization = [
      "roles/storage.objectAdmin",
      "roles/cloudtranslate.user",
      "roles/aiplatform.user",
      "roles/datastore.user",
      "roles/pubsub.subscriber",
    ]
    deployer = [
      "roles/artifactregistry.writer",
      "roles/run.admin",
      "roles/iam.serviceAccountUser",
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

# Cloud Storage's service agent must be able to publish object notifications.
resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.topics["video_events"].name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"
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

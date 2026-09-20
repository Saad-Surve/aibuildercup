data "archive_file" "killswitch" {
  type        = "zip"
  source_dir  = "${path.module}/killswitch"
  output_path = "${path.module}/killswitch.zip"
}

resource "google_storage_bucket_object" "killswitch" {
  name   = "functions/killswitch-${data.archive_file.killswitch.output_md5}.zip"
  bucket = google_storage_bucket.buckets["temp"].name
  source = data.archive_file.killswitch.output_path
}

resource "google_pubsub_topic" "budget_alerts" {
  name    = "budget-alerts"
  project = var.project_id
}

resource "google_service_account" "budget_guard" {
  account_id   = "creator-studio-budget-guard"
  display_name = "Creator Studio Budget Guard"
  project      = var.project_id
}

resource "google_billing_account_iam_member" "guard_billing_admin" {
  billing_account_id = var.billing_account_id
  role               = "roles/billing.admin"
  member             = "serviceAccount:${google_service_account.budget_guard.email}"
}

resource "google_project_iam_member" "guard_eventarc_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.budget_guard.email}"
}

resource "google_project_iam_member" "guard_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.budget_guard.email}"
}

resource "google_project_iam_member" "guard_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.budget_guard.email}"
}

resource "google_cloudfunctions2_function" "killswitch" {
  name     = "budget-killswitch"
  project  = var.project_id
  location = var.region

  build_config {
    runtime     = "python312"
    entry_point = "disable_billing_on_budget"

    source {
      storage_source {
        bucket = google_storage_bucket.buckets["temp"].name
        object = google_storage_bucket_object.killswitch.name
      }
    }
  }

  service_config {
    max_instance_count    = 1
    available_memory      = "256M"
    timeout_seconds       = 60
    service_account_email = google_service_account.budget_guard.email

    environment_variables = {
      PROJECT_ID = var.project_id
      DRY_RUN    = var.killswitch_dry_run ? "true" : "false"
    }
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.budget_alerts.id
    retry_policy   = "RETRY_POLICY_DO_NOT_RETRY"
  }

  depends_on = [
    google_project_iam_member.guard_eventarc_receiver,
    google_project_iam_member.guard_run_invoker,
  ]
}

resource "google_billing_budget" "cap" {
  billing_account = var.billing_account_id
  display_name    = "Hackathon cap"

  budget_filter {
    projects = ["projects/${var.project_id}"]
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = var.budget_amount
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.8
  }
  threshold_rules {
    threshold_percent = 1.0
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    pubsub_topic   = google_pubsub_topic.budget_alerts.id
    schema_version = "1.0"
  }
}

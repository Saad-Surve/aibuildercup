locals {
  topics = {
    video_events        = "video-events"
    transcription_events = "transcription-events"
    analysis_events     = "analysis-events"
    social_sync_events  = "social-sync-events"
    artifact_events     = "artifact-events"
    localization_events = "localization-events"
  }

  dlq_topics = {
    video_events       = "video-events-dlq"
    analysis_events    = "analysis-events-dlq"
    social_sync_events = "social-sync-events-dlq"
    artifact_events    = "artifact-events-dlq"
  }
}

resource "google_pubsub_topic" "topics" {
  for_each = local.topics
  name     = each.value
  project  = var.project_id
}

resource "google_pubsub_topic" "dlq" {
  for_each = local.dlq_topics
  name     = each.value
  project  = var.project_id
}

resource "google_pubsub_subscription" "transcribe_worker" {
  # Push subscription: the trigger of record for transcription is the GCS `object finalized`
  # notification on the media bucket (below) -> video-events -> this push -> the API handler.
  # Only created once `api_url` is known.
  count   = var.api_url != "" ? 1 : 0
  name    = "transcribe-worker-sub"
  topic   = google_pubsub_topic.topics["video_events"].name
  project = var.project_id

  ack_deadline_seconds = 600

  push_config {
    push_endpoint = "${trimsuffix(var.api_url, "/")}/api/internal/pubsub/video-events"

    oidc_token {
      service_account_email = google_service_account.runtime["transcribe"].email
      audience              = trimsuffix(var.api_url, "/")
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq["video_events"].id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

# Every finalized object in the media bucket is announced; the API handler ignores anything that
# is not a source video.
resource "google_storage_notification" "video_finalized" {
  bucket         = google_storage_bucket.buckets["media"].name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.topics["video_events"].id
  event_types    = ["OBJECT_FINALIZE"]

  depends_on = [google_pubsub_topic_iam_member.gcs_publisher]
}

resource "google_pubsub_subscription" "analysis_worker" {
  name                 = "analysis-worker-sub"
  project              = var.project_id
  topic                = google_pubsub_topic.topics["analysis_events"].name
  ack_deadline_seconds = 600

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq["analysis_events"].id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

resource "google_pubsub_subscription" "social_sync_worker" {
  name                 = "social-sync-worker-sub"
  project              = var.project_id
  topic                = google_pubsub_topic.topics["social_sync_events"].name
  ack_deadline_seconds = 600

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq["social_sync_events"].id
    max_delivery_attempts = 5
  }
}

resource "google_pubsub_subscription" "media_worker" {
  name                 = "media-worker-sub"
  project              = var.project_id
  topic                = google_pubsub_topic.topics["artifact_events"].name
  ack_deadline_seconds = 600

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq["artifact_events"].id
    max_delivery_attempts = 5
  }
}

resource "google_pubsub_subscription" "localization_worker" {
  name                 = "localization-worker-sub"
  project              = var.project_id
  topic                = google_pubsub_topic.topics["localization_events"].name
  ack_deadline_seconds = 600
}

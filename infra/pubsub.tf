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
  name                 = "transcribe-worker-sub"
  project              = var.project_id
  topic                = google_pubsub_topic.topics["video_events"].name
  ack_deadline_seconds = 600

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq["video_events"].id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
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

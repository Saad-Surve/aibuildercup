resource "google_bigquery_dataset" "social" {
  dataset_id                 = "creator_studio_social"
  project                    = var.project_id
  location                   = var.region
  delete_contents_on_destroy = true
}

resource "google_bigquery_dataset" "ai" {
  dataset_id                 = "creator_studio_ai"
  project                    = var.project_id
  location                   = var.region
  delete_contents_on_destroy = true
}

resource "google_bigquery_dataset" "audit" {
  dataset_id                 = "creator_studio_audit"
  project                    = var.project_id
  location                   = var.region
  delete_contents_on_destroy = true
}

resource "google_bigquery_table" "posts" {
  dataset_id          = google_bigquery_dataset.social.dataset_id
  table_id            = "posts"
  project             = var.project_id
  deletion_protection = false
  schema = jsonencode([
    { name = "owner_uid", type = "STRING", mode = "REQUIRED" },
    { name = "platform", type = "STRING", mode = "REQUIRED" },
    { name = "external_id", type = "STRING", mode = "REQUIRED" },
    { name = "title", type = "STRING", mode = "NULLABLE" },
    { name = "published_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "raw_storage_path", type = "STRING", mode = "NULLABLE" },
  ])
  clustering = ["owner_uid", "platform"]
}

resource "google_bigquery_table" "metrics" {
  dataset_id          = google_bigquery_dataset.social.dataset_id
  table_id            = "metrics"
  project             = var.project_id
  deletion_protection = false
  schema = jsonencode([
    { name = "owner_uid", type = "STRING", mode = "REQUIRED" },
    { name = "platform", type = "STRING", mode = "REQUIRED" },
    { name = "post_external_id", type = "STRING", mode = "REQUIRED" },
    { name = "observed_date", type = "DATE", mode = "REQUIRED" },
    { name = "views", type = "INT64", mode = "NULLABLE" },
    { name = "likes", type = "INT64", mode = "NULLABLE" },
    { name = "comments", type = "INT64", mode = "NULLABLE" },
    { name = "shares", type = "INT64", mode = "NULLABLE" },
  ])
  time_partitioning {
    type  = "DAY"
    field = "observed_date"
  }
  clustering = ["owner_uid", "platform"]
}

resource "google_bigquery_table" "comments" {
  dataset_id          = google_bigquery_dataset.social.dataset_id
  table_id            = "comments"
  project             = var.project_id
  deletion_protection = false
  schema = jsonencode([
    { name = "owner_uid", type = "STRING", mode = "REQUIRED" },
    { name = "platform", type = "STRING", mode = "REQUIRED" },
    { name = "external_id", type = "STRING", mode = "REQUIRED" },
    { name = "post_external_id", type = "STRING", mode = "NULLABLE" },
    { name = "text", type = "STRING", mode = "NULLABLE" },
    { name = "published_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
  clustering = ["owner_uid", "platform"]
}

resource "google_bigquery_table" "audience_aggregates" {
  dataset_id          = google_bigquery_dataset.social.dataset_id
  table_id            = "audience_aggregates"
  project             = var.project_id
  deletion_protection = false
  schema = jsonencode([
    { name = "owner_uid", type = "STRING", mode = "REQUIRED" },
    { name = "platform", type = "STRING", mode = "REQUIRED" },
    { name = "period_start", type = "DATE", mode = "NULLABLE" },
    { name = "period_end", type = "DATE", mode = "NULLABLE" },
    { name = "dimension", type = "STRING", mode = "NULLABLE" },
    { name = "bucket", type = "STRING", mode = "NULLABLE" },
    { name = "value", type = "FLOAT64", mode = "NULLABLE" },
  ])
  clustering = ["owner_uid", "platform"]
}

resource "google_bigquery_table" "comment_sentiment" {
  dataset_id          = google_bigquery_dataset.ai.dataset_id
  table_id            = "comment_sentiment"
  project             = var.project_id
  deletion_protection = false
  schema = jsonencode([
    { name = "owner_uid", type = "STRING", mode = "REQUIRED" },
    { name = "platform", type = "STRING", mode = "REQUIRED" },
    { name = "comment_external_id", type = "STRING", mode = "REQUIRED" },
    { name = "label", type = "STRING", mode = "NULLABLE" },
    { name = "score", type = "FLOAT64", mode = "NULLABLE" },
    { name = "model", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
  clustering = ["owner_uid", "platform"]
}

resource "google_bigquery_table" "agent_runs" {
  dataset_id          = google_bigquery_dataset.ai.dataset_id
  table_id            = "agent_runs"
  project             = var.project_id
  deletion_protection = false
  schema = jsonencode([
    { name = "owner_uid", type = "STRING", mode = "REQUIRED" },
    { name = "project_id", type = "STRING", mode = "NULLABLE" },
    { name = "analysis_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "dimension", type = "STRING", mode = "NULLABLE" },
    { name = "model", type = "STRING", mode = "NULLABLE" },
    { name = "prompt_version", type = "STRING", mode = "NULLABLE" },
    { name = "input_tokens", type = "INT64", mode = "NULLABLE" },
    { name = "output_tokens", type = "INT64", mode = "NULLABLE" },
    { name = "latency_ms", type = "INT64", mode = "NULLABLE" },
    { name = "cost_estimate_usd", type = "FLOAT64", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
  clustering = ["owner_uid", "dimension"]
}

resource "google_bigquery_table" "glossary_terms" {
  dataset_id          = google_bigquery_dataset.ai.dataset_id
  table_id            = "glossary_terms"
  project             = var.project_id
  deletion_protection = false
  schema = jsonencode([
    { name = "term", type = "STRING", mode = "REQUIRED" },
    { name = "source_lang", type = "STRING", mode = "REQUIRED" },
    { name = "target_lang", type = "STRING", mode = "REQUIRED" },
    { name = "category", type = "STRING", mode = "NULLABLE" },
    { name = "version", type = "INT64", mode = "NULLABLE" },
  ])
  clustering = ["source_lang", "target_lang", "category"]
}

resource "google_bigquery_table" "translation_traps" {
  dataset_id          = google_bigquery_dataset.ai.dataset_id
  table_id            = "translation_traps"
  project             = var.project_id
  deletion_protection = false
  schema = jsonencode([
    { name = "category", type = "STRING", mode = "NULLABLE" },
    { name = "source", type = "STRING", mode = "REQUIRED" },
    { name = "recommended", type = "STRING", mode = "NULLABLE" },
    { name = "notes", type = "STRING", mode = "NULLABLE" },
    { name = "version", type = "INT64", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "data_access_events" {
  dataset_id          = google_bigquery_dataset.audit.dataset_id
  table_id            = "data_access_events"
  project             = var.project_id
  deletion_protection = false
  schema = jsonencode([
    { name = "actor_type", type = "STRING", mode = "NULLABLE" },
    { name = "actor_id", type = "STRING", mode = "NULLABLE" },
    { name = "action", type = "STRING", mode = "NULLABLE" },
    { name = "resource_type", type = "STRING", mode = "NULLABLE" },
    { name = "resource_id", type = "STRING", mode = "NULLABLE" },
    { name = "owner_uid_hash", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
}

output "buckets" {
  value = { for k, b in google_storage_bucket.buckets : k => b.name }
}

output "bigquery_datasets" {
  value = {
    social = google_bigquery_dataset.social.dataset_id
    ai     = google_bigquery_dataset.ai.dataset_id
    audit  = google_bigquery_dataset.audit.dataset_id
  }
}

output "pubsub_topics" {
  value = { for k, t in google_pubsub_topic.topics : k => t.name }
}

output "service_accounts" {
  value = { for k, s in google_service_account.runtime : k => s.email }
}

output "artifact_registry" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}"
}

output "kms_key" {
  value = google_kms_crypto_key.user_token_key.id
}

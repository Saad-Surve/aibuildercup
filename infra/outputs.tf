output "buckets" {
  value = { for k, b in google_storage_bucket.buckets : k => b.name }
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

output "wif_provider" {
  description = "Set as the GCP_WIF_PROVIDER repository variable."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  description = "Set as the GCP_DEPLOY_SA repository variable."
  value       = google_service_account.runtime["deployer"].email
}

output "registry" {
  description = "Artifact Registry prefix used for image tags."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}"
}

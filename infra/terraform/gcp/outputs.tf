output "cloud_run_service_url" {
  description = "URL of the Cloud Run service for Slack events"
  value       = google_cloud_run_v2_service.slack_events.uri
}

output "cloud_run_job_name" {
  description = "Name of the Cloud Run job for reply generation"
  value       = google_cloud_run_v2_job.reply_generator.name
}

output "service_account_email" {
  description = "Email of the Cloud Run service account"
  value       = google_service_account.cloudrun.email
}

output "artifact_registry_repository" {
  description = "Artifact Registry repository name"
  value       = google_artifact_registry_repository.reply_bot.name
}

output "async_generation_endpoint" {
  description = "Endpoint URL for async generation (for Lambda configuration)"
  value       = "${google_cloud_run_v2_service.slack_events.uri}/async/generate"
}

output "slack_request_url" {
  description = "Slack Request URL (for Slack app configuration)"
  value       = "${google_cloud_run_v2_service.slack_events.uri}/slack/events"
}

output "secret_names" {
  description = "Names of created secrets"
  value = {
    slack_signing = google_secret_manager_secret.slack_signing.secret_id
    slack_bot_token = google_secret_manager_secret.slack_bot_token.secret_id
    openai_api_key = google_secret_manager_secret.openai_api_key.secret_id
  }
}

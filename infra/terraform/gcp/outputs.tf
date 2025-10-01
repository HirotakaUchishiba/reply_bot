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

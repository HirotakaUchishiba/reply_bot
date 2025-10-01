# Google Cloud Run Service for Slack Events
resource "google_cloud_run_v2_service" "slack_events" {
  name     = "reply-bot-slack-events-${var.environment}"
  location = var.gcp_region
  project  = var.gcp_project_id

  template {
    service_account = google_service_account.cloudrun.email
    
    containers {
      image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.reply_bot.name}/slack-events:latest"
      
      ports {
        container_port = 8080
      }
      
      env {
        name  = "GCP_PROJECT_ID"
        value = var.gcp_project_id
      }
      
      env {
        name  = "GCP_REGION"
        value = var.gcp_region
      }
      
      env {
        name  = "CLOUD_RUN_JOB_NAME"
        value = google_cloud_run_v2_job.reply_generator.name
      }
      
      env {
        name  = "SERVICE_ACCOUNT_EMAIL"
        value = google_service_account.cloudrun.email
      }
      
      env {
        name  = "SLACK_SIGNING_SECRET_NAME"
        value = google_secret_manager_secret.slack_signing.secret_id
      }
      
      env {
        name  = "STAGE"
        value = var.environment
      }
      
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
    
    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# Google Cloud Run Job for Reply Generation
resource "google_cloud_run_v2_job" "reply_generator" {
  name     = "reply-bot-generator-${var.environment}"
  location = var.gcp_region
  project  = var.gcp_project_id

  template {
    template {
      service_account = google_service_account.cloudrun.email
      
      containers {
        image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.reply_bot.name}/reply-generator:latest"
        
        env {
          name  = "GCP_PROJECT_ID"
          value = var.gcp_project_id
        }
        
        env {
          name  = "GCP_REGION"
          value = var.gcp_region
        }
        
        env {
          name  = "OPENAI_API_KEY_SECRET_NAME"
          value = google_secret_manager_secret.openai_api_key.secret_id
        }
        
        env {
          name  = "SLACK_BOT_TOKEN_SECRET_NAME"
          value = google_secret_manager_secret.slack_bot_token.secret_id
        }
        
        env {
          name  = "AWS_ACCESS_KEY_ID"
          value = var.aws_access_key_id
        }
        
        env {
          name  = "AWS_SECRET_ACCESS_KEY"
          value = var.aws_secret_access_key
        }
        
        env {
          name  = "AWS_REGION"
          value = var.aws_region
        }
        
        env {
          name  = "DDB_TABLE_NAME"
          value = var.ddb_table_name
        }
        
        resources {
          limits = {
            cpu    = "2"
            memory = "1Gi"
          }
        }
      }
      
      timeout = "300s"
      
      max_retries = 3
    }
  }
}

# Service Account for Cloud Run
resource "google_service_account" "cloudrun" {
  account_id   = "reply-bot-cloudrun-${var.environment}"
  display_name = "Reply Bot Cloud Run Service Account"
  project      = var.gcp_project_id
}

# IAM bindings for Cloud Run Service Account
resource "google_project_iam_member" "cloudrun_secret_accessor" {
  project = var.gcp_project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

resource "google_project_iam_member" "cloudrun_job_executor" {
  project = var.gcp_project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

# Artifact Registry Repository
resource "google_artifact_registry_repository" "reply_bot" {
  location      = var.gcp_region
  repository_id = "reply-bot"
  description   = "Docker repository for Reply Bot"
  format        = "DOCKER"
  project       = var.gcp_project_id
}

# Secret Manager Secrets
resource "google_secret_manager_secret" "slack_signing" {
  secret_id = "slack-signing-secret-${var.environment}"
  project   = var.gcp_project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "slack_bot_token" {
  secret_id = "slack-bot-token-${var.environment}"
  project   = var.gcp_project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "openai-api-key-${var.environment}"
  project   = var.gcp_project_id

  replication {
    auto {}
  }
}

# IAM for Cloud Run to access secrets
resource "google_secret_manager_secret_iam_member" "slack_signing_access" {
  secret_id = google_secret_manager_secret.slack_signing.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloudrun.email}"
  project   = var.gcp_project_id
}

resource "google_secret_manager_secret_iam_member" "slack_bot_token_access" {
  secret_id = google_secret_manager_secret.slack_bot_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloudrun.email}"
  project   = var.gcp_project_id
}

resource "google_secret_manager_secret_iam_member" "openai_api_key_access" {
  secret_id = google_secret_manager_secret.openai_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloudrun.email}"
  project   = var.gcp_project_id
}

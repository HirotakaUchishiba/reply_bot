# Google Cloud Run Service for Slack Events
resource "google_cloud_run_v2_service" "slack_events" {
  name     = "reply-bot-slack-events-${var.environment}"
  location = var.gcp_region
  project  = var.gcp_project_id

  template {
    service_account = google_service_account.cloudrun.email
    
    annotations = {
      "run.googleapis.com/ingress" = "all"
    }
    
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
        name  = "SLACK_BOT_TOKEN_SECRET_NAME"
        value = google_secret_manager_secret.slack_bot_token.secret_id
      }
      
      env {
        name  = "STAGE"
        value = var.environment
      }
      
      env {
        name  = "AUTH_TOKEN"
        value = var.auth_token
      }
      
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
      
      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 10
        timeout_seconds      = 5
        period_seconds       = 10
        failure_threshold    = 3
      }
      
      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 30
        timeout_seconds      = 5
        period_seconds       = 30
        failure_threshold    = 3
      }
    }
    
    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }
    
    timeout = "60s"
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
        image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.reply_bot.name}/job-worker:latest"
        
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
          name  = "AWS_REGION"
          value = var.aws_region
        }
        
        env {
          name  = "AWS_ROLE_ARN"
          value = var.aws_workload_identity_role_arn
        }
        
        env {
          name  = "GCP_SERVICE_ACCOUNT_EMAIL"
          value = google_service_account.cloudrun.email
        }
        
        env {
          name  = "WORKLOAD_IDENTITY_PROVIDER"
          value = google_iam_workload_identity_pool_provider.aws_provider.name
        }
        
        env {
          name  = "DDB_TABLE_NAME"
          value = var.ddb_table_name
        }
        
        env {
          name  = "OPENAI_TIMEOUT"
          value = "30"
        }
        
        env {
          name  = "LOG_LEVEL"
          value = "INFO"
        }
        
        env {
          name  = "AWS_ACCESS_KEY_ID_SECRET_NAME"
          value = google_secret_manager_secret.aws_access_key_id.secret_id
        }
        
        env {
          name  = "AWS_SECRET_ACCESS_KEY_SECRET_NAME"
          value = google_secret_manager_secret.aws_secret_access_key.secret_id
        }
        
        env {
          name  = "SENDER_EMAIL_ADDRESS"
          value = var.sender_email_address
        }
        
        env {
          name  = "SLACK_CHANNEL_ID"
          value = var.slack_channel_id
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

# Workload Identity Pool for AWS integration
resource "google_iam_workload_identity_pool" "aws_pool" {
  workload_identity_pool_id = "aws-pool-${var.environment}"
  display_name              = "AWS Workload Identity Pool"
  description               = "Workload Identity Pool for AWS integration"
  project                   = var.gcp_project_id
}

# Workload Identity Pool Provider for AWS
resource "google_iam_workload_identity_pool_provider" "aws_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.aws_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "aws-provider"
  display_name                       = "AWS Provider"
  description                        = "AWS OIDC Provider for Workload Identity"
  project                            = var.gcp_project_id

  attribute_mapping = {
    "google.subject"        = "assertion.sub"
    "attribute.aws_account" = "assertion.aud"
  }

  oidc {
    issuer_uri = "https://accounts.google.com"
  }
}

# Allow Cloud Run Service Account to impersonate AWS IAM Role
resource "google_service_account_iam_binding" "cloudrun_aws_impersonation" {
  service_account_id = google_service_account.cloudrun.name
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${google_service_account.cloudrun.email}",
  ]
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

resource "google_secret_manager_secret" "aws_access_key_id" {
  secret_id = "aws-access-key-id-${var.environment}"
  project   = var.gcp_project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "aws_secret_access_key" {
  secret_id = "aws-secret-access-key-${var.environment}"
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

resource "google_secret_manager_secret_iam_member" "aws_access_key_id_access" {
  secret_id = google_secret_manager_secret.aws_access_key_id.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloudrun.email}"
  project   = var.gcp_project_id
}

resource "google_secret_manager_secret_iam_member" "aws_secret_access_key_access" {
  secret_id = google_secret_manager_secret.aws_secret_access_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloudrun.email}"
  project   = var.gcp_project_id
}

variable "secret_name_openai_api_key" {
  type        = string
  description = "Secrets Manager name for OpenAI API key"
  default     = "reply-bot/openai/api-key"
}

variable "secret_name_slack_app" {
  type        = string
  description = "Secrets Manager name for Slack app credentials"
  default     = "reply-bot/slack/app-creds"
}

variable "secret_name_gmail_oauth" {
  type        = string
  description = "Secrets Manager name for Gmail OAuth credentials"
  default     = "reply-bot/gmail/oauth"
}

resource "aws_secretsmanager_secret" "openai_api_key" {
  name       = var.secret_name_openai_api_key
  kms_key_id = null
}

resource "aws_secretsmanager_secret" "slack_app" {
  name       = var.secret_name_slack_app
  kms_key_id = null
}

resource "aws_secretsmanager_secret" "gmail_oauth" {
  name       = var.secret_name_gmail_oauth
  kms_key_id = null
}

# Slack signing secret
variable "secret_name_slack_signing" {
  type        = string
  description = "Secrets Manager name for Slack signing secret"
  default     = "reply-bot/slack/signing-secret"
}

resource "aws_secretsmanager_secret" "slack_signing" {
  name       = var.secret_name_slack_signing
  kms_key_id = null
}


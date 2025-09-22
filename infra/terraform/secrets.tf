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

resource "aws_secretsmanager_secret" "openai_api_key" {
  name       = var.secret_name_openai_api_key
  kms_key_id = null
}

resource "aws_secretsmanager_secret" "slack_app" {
  name       = var.secret_name_slack_app
  kms_key_id = null
}

output "secrets_openai_arn" {
  value = aws_secretsmanager_secret.openai_api_key.arn
}

output "secrets_slack_app_arn" {
  value = aws_secretsmanager_secret.slack_app.arn
}

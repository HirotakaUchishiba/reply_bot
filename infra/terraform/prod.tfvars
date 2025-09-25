aws_region = "ap-northeast-1"

# Terraform state configuration (to be set via GitHub Secrets)
tf_state_bucket         = "your-terraform-state-bucket"
tf_state_key_prefix     = "reply-bot"
tf_state_dynamodb_table = "your-terraform-locks-table"

# DynamoDB configuration
ddb_table_name      = "reply-bot-context-prod"
ddb_ttl_attribute   = "ttl_epoch"

# Secrets Manager configuration
secret_name_openai_api_key = "reply-bot/prod/openai/api-key"
secret_name_slack_app      = "reply-bot/prod/slack/app-creds"

# SES configuration
ses_rule_set_name = "reply-bot-prod"
ses_recipients    = ["support@example.com"]

# Application configuration (to be set via GitHub Secrets)
sender_email_address = "support@your-reply-domain.com"
slack_channel_id     = "C0PRODCHANID"

# Monitoring configuration
alarm_lambda_error_threshold = 1
alarm_apigw_5xx_threshold    = 1

aws_region = "ap-northeast-1"

# Terraform state configuration (実際の値に置き換えました)
tf_state_bucket         = "reply-bot-terraform-state-20241224"
tf_state_key_prefix     = "reply-bot"
tf_state_dynamodb_table = "reply-bot-terraform-state-lock"

# DynamoDB configuration
ddb_table_name      = "reply-bot-context-staging"
ddb_ttl_attribute   = "ttl_epoch"

# Secrets Manager configuration
secret_name_openai_api_key = "reply-bot/stg/openai/api-key"
secret_name_slack_app      = "reply-bot/stg/slack/app-creds"

# SES configuration (テスト用設定)
ses_rule_set_name = "reply-bot-staging"
ses_recipients    = ["hirotaka19990821@gmail.com"]  # テスト用Gmailアドレス

# Application configuration (テスト用設定)
sender_email_address = "hirotaka19990821@gmail.com"  # テスト用Gmailアドレス
slack_channel_id     = "C01234ABCDE"  # 実際のSlackチャンネルIDに置き換えてください

# SES Domain Authentication (テスト用 - ドメイン認証を無効化)
# ses_domain_name = "staging.your-reply-domain.com"
# ses_dmarc_email = "dmarc@your-reply-domain.com"

# Monitoring configuration
alarm_lambda_error_threshold = 1
alarm_apigw_5xx_threshold    = 1

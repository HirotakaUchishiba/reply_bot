data "archive_file" "lambda_package" {
  type        = "zip"
  source_dir  = "${path.root}/../../src/app"
  output_path = "${path.module}/.dist/lambda.zip"
}

resource "aws_lambda_function" "app" {
  function_name = "reply-bot-${terraform.workspace}"
  role          = aws_iam_role.lambda_exec.arn
  runtime       = "python3.11"
  handler       = "handler.handler"

  filename         = data.archive_file.lambda_package.output_path
  source_code_hash = data.archive_file.lambda_package.output_base64sha256

  timeout     = 30
  memory_size = 256

  environment {
    variables = {
      STAGE                        = terraform.workspace
      DDB_TABLE_NAME               = local.effective_ddb_table_name
      OPENAI_API_KEY_SECRET_ARN    = aws_secretsmanager_secret.openai_api_key.arn
      SLACK_APP_SECRET_ARN         = aws_secretsmanager_secret.slack_app.arn
      SLACK_SIGNING_SECRET_ARN     = aws_secretsmanager_secret.slack_signing.arn
      SENDER_EMAIL_ADDRESS         = var.sender_email_address
      SLACK_CHANNEL_ID             = var.slack_channel_id
      GMAIL_OAUTH_SECRET_ARN       = aws_secretsmanager_secret.gmail_oauth.arn
      SES_INBOUND_BUCKET_NAME      = aws_s3_bucket.inbound.bucket
      SES_INBOUND_PREFIX           = "inbound/"
    }
  }

  layers = [
    aws_lambda_layer_version.presidio.arn
  ]

  dead_letter_config {
    target_arn = aws_sqs_queue.dlq.arn
  }
}

# Gmail Poller Lambda (shares same source package, different handler)
resource "aws_lambda_function" "gmail_poller" {
  function_name = "reply-bot-gmail-poller-${terraform.workspace}"
  role          = aws_iam_role.lambda_exec.arn
  runtime       = "python3.11"
  handler       = "gmail_poller.handler"

  filename         = data.archive_file.lambda_package.output_path
  source_code_hash = data.archive_file.lambda_package.output_base64sha256

  timeout     = 30
  memory_size = 256

  environment {
    variables = {
      STAGE                        = terraform.workspace
      DDB_TABLE_NAME               = local.effective_ddb_table_name
      OPENAI_API_KEY_SECRET_ARN    = aws_secretsmanager_secret.openai_api_key.arn
      SLACK_APP_SECRET_ARN         = aws_secretsmanager_secret.slack_app.arn
      SLACK_SIGNING_SECRET_ARN     = aws_secretsmanager_secret.slack_signing.arn
      SENDER_EMAIL_ADDRESS         = var.sender_email_address
      SLACK_CHANNEL_ID             = var.slack_channel_id
      GMAIL_OAUTH_SECRET_ARN       = aws_secretsmanager_secret.gmail_oauth.arn
    }
  }

  layers = [
    aws_lambda_layer_version.presidio.arn
  ]
}

resource "aws_cloudwatch_event_rule" "gmail_poll_schedule" {
  name                = "reply-bot-gmail-poll-${terraform.workspace}"
  schedule_expression = "rate(60 minutes)"
}

resource "aws_cloudwatch_event_target" "gmail_poll_target" {
  rule      = aws_cloudwatch_event_rule.gmail_poll_schedule.name
  target_id = "gmail-poller"
  arn       = aws_lambda_function.gmail_poller.arn
}

resource "aws_lambda_permission" "allow_events_invoke_gmail_poller" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.gmail_poller.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.gmail_poll_schedule.arn
}

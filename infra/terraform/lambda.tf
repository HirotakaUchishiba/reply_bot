data "archive_file" "lambda_package" {
  type        = "zip"
  source_dir  = "${path.root}/../../src/lambda"
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
      SENDER_EMAIL_ADDRESS         = var.sender_email_address
      SLACK_CHANNEL_ID             = var.slack_channel_id
    }
  }

  layers = [
    aws_lambda_layer_version.presidio.arn
  ]

  dead_letter_config {
    target_arn = aws_sqs_queue.dlq.arn
  }
}

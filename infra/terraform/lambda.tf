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
      STAGE = terraform.workspace
    }
  }

  layers = [
    aws_lambda_layer_version.presidio.arn
  ]

  dead_letter_config {
    target_arn = aws_sqs_queue.dlq.arn
  }
}

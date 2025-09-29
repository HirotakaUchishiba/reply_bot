data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_exec" {
  name               = "reply-bot-lambda-exec-${terraform.workspace}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "lambda_logs_policy" {
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "lambda_logs" {
  name   = "reply-bot-lambda-logs-${terraform.workspace}"
  policy = data.aws_iam_policy_document.lambda_logs_policy.json
}

resource "aws_iam_role_policy_attachment" "lambda_logs_attach" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_logs.arn
}

# Placeholder policies for later principle of least privilege attachments
data "aws_iam_policy_document" "lambda_app_policy" {
  statement {
    sid = "DynamoDB"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan"
    ]
    resources = [
      aws_dynamodb_table.context.arn
    ]
  }

  statement {
    sid = "SecretsManager"
    actions = [
      "secretsmanager:GetSecretValue"
    ]
    resources = [
      aws_secretsmanager_secret.openai_api_key.arn,
      aws_secretsmanager_secret.slack_app.arn,
      aws_secretsmanager_secret.gmail_oauth.arn,
      aws_secretsmanager_secret.slack_signing.arn
    ]
  }

  statement {
    sid = "SES"
    actions = [
      "ses:SendEmail",
      "ses:SendRawEmail"
    ]
    resources = ["*"]
  }

  statement {
    sid = "SQS"
    actions = [
      "sqs:SendMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl"
    ]
    resources = [
      aws_sqs_queue.dlq.arn
    ]
  }

  statement {
    sid = "S3InboundRead"
    actions = [
      "s3:GetObject",
      "s3:ListBucket"
    ]
    resources = [
      aws_s3_bucket.inbound.arn,
      "${aws_s3_bucket.inbound.arn}/*"
    ]
  }
}

resource "aws_iam_policy" "lambda_app" {
  name   = "reply-bot-lambda-app-${terraform.workspace}"
  policy = data.aws_iam_policy_document.lambda_app_policy.json
}

resource "aws_iam_role_policy_attachment" "lambda_app_attach" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_app.arn
}



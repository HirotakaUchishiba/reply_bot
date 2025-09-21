resource "aws_sqs_queue" "dlq" {
  name                      = "reply-bot-dlq-${terraform.workspace}"
  message_retention_seconds = 1209600 # 14 days
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "main" {
  name                      = "reply-bot-queue-${terraform.workspace}"
  message_retention_seconds = 345600 # 4 days
  sqs_managed_sse_enabled   = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })
}



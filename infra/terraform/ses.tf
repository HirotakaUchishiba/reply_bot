variable "ses_rule_set_name" {
  type        = string
  description = "SES active receipt rule set name"
  default     = "reply-bot-rule-set"
}

variable "ses_recipients" {
  type        = list(string)
  description = "List of recipient email addresses to match"
  default     = ["support@your-reply-domain.com"]
}

resource "aws_ses_receipt_rule_set" "main" {
  rule_set_name = var.ses_rule_set_name
}

resource "aws_ses_active_receipt_rule_set" "active" {
  rule_set_name = aws_ses_receipt_rule_set.main.rule_set_name
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "inbound" {
  bucket = "reply-bot-inbound-${terraform.workspace}"
}

resource "aws_s3_bucket_public_access_block" "inbound" {
  bucket                  = aws_s3_bucket.inbound.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "ses_put_object" {
  statement {
    sid = "AllowSESPuts"
    actions = ["s3:PutObject"]
    principals {
      type        = "Service"
      identifiers = ["ses.amazonaws.com"]
    }
    resources = ["${aws_s3_bucket.inbound.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:Referer"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_s3_bucket_policy" "inbound" {
  bucket = aws_s3_bucket.inbound.id
  policy = data.aws_iam_policy_document.ses_put_object.json
}

resource "aws_ses_receipt_rule" "lambda_route" {
  name          = "route-to-lambda"
  rule_set_name = aws_ses_receipt_rule_set.main.rule_set_name
  enabled       = true
  recipients    = var.ses_recipients
  scan_enabled  = true
  tls_policy    = "Optional"

  s3_action {
    bucket_name      = aws_s3_bucket.inbound.bucket
    object_key_prefix = "inbound/"
    position         = 1
  }

  # Lambda will be invoked by S3 ObjectCreated notification instead
}

resource "aws_s3_bucket_notification" "inbound" {
  bucket = aws_s3_bucket.inbound.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.app.arn
    events              = ["s3:ObjectCreated:Put"]
    filter_prefix       = "inbound/"
  }

  depends_on = [aws_lambda_permission.allow_s3_invoke]
}

resource "aws_lambda_permission" "allow_s3_invoke" {
  statement_id  = "AllowS3Invocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.inbound.arn
}



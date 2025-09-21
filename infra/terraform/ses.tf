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

resource "aws_ses_receipt_rule" "lambda_route" {
  name          = "route-to-lambda"
  rule_set_name = aws_ses_receipt_rule_set.main.rule_set_name
  enabled       = true
  recipients    = var.ses_recipients
  scan_enabled  = true
  tls_policy    = "Optional"

  lambda_action {
    function_arn    = aws_lambda_function.app.arn
    invocation_type = "Event"
    position        = 1
  }
}

resource "aws_lambda_permission" "allow_ses_invoke" {
  statement_id  = "AllowExecutionFromSES"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app.function_name
  principal     = "ses.amazonaws.com"
  source_arn    = aws_ses_receipt_rule.lambda_route.arn
}



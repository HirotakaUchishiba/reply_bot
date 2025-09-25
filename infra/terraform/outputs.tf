output "api_gateway_url" {
  description = "API Gateway URL for Slack events endpoint"
  value       = "${aws_apigatewayv2_api.http.api_endpoint}/slack/events"
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.app.function_name
}

output "dynamodb_table_name" {
  description = "DynamoDB table name for context storage"
  value       = aws_dynamodb_table.context.name
}

output "ses_rule_set_name" {
  description = "SES receipt rule set name"
  value       = aws_ses_receipt_rule_set.main.rule_set_name
}

output "secrets_openai_arn" {
  description = "OpenAI API key secret ARN"
  value       = aws_secretsmanager_secret.openai_api_key.arn
}

output "secrets_slack_app_arn" {
  description = "Slack app credentials secret ARN"
  value       = aws_secretsmanager_secret.slack_app.arn
}

output "cloudwatch_dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

variable "alarm_lambda_error_threshold" {
  type        = number
  description = "Lambda Errors alarm threshold (per 5 minutes)"
  default     = 1
}

variable "alarm_apigw_5xx_threshold" {
  type        = number
  description = "API Gateway 5XXError alarm threshold (per 5 minutes)"
  default     = 1
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "reply-bot-${terraform.workspace}"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "Lambda Errors"
          metrics = [["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.app.function_name]]
          period  = 300
          stat    = "Sum"
          region  = var.aws_region
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "API Gateway 5XX"
          metrics = [["AWS/ApiGateway", "5XXError", "ApiId", aws_apigatewayv2_api.http.id]]
          period  = 300
          stat    = "Sum"
          region  = var.aws_region
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "SQS DLQ ApproximateNumberOfMessagesVisible"
          metrics = [["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.dlq.name]]
          period  = 300
          stat    = "Maximum"
          region  = var.aws_region
          view    = "timeSeries"
        }
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "reply-bot-${terraform.workspace}-lambda-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.alarm_lambda_error_threshold
  dimensions = {
    FunctionName = aws_lambda_function.app.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "apigw_5xx" {
  alarm_name          = "reply-bot-${terraform.workspace}-apigw-5xx"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = var.alarm_apigw_5xx_threshold
  dimensions = {
    ApiId = aws_apigatewayv2_api.http.id
  }
}

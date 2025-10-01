# AWS IAM Role for Cloud Run Job Worker
# This will be created in AWS account, not GCP
# This file serves as documentation and can be applied separately

# IAM Role for Workload Identity
resource "aws_iam_role" "cloudrun_workload_identity" {
  name = "reply-bot-cloudrun-workload-identity-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${var.aws_account_id}:oidc-provider/${var.aws_oidc_provider_id}"
        }
        Condition = {
          StringEquals = {
            "${var.aws_oidc_provider_id}:sub" = "system:serviceaccount:${var.gcp_project_id}:${google_service_account.cloudrun.email}"
            "${var.aws_oidc_provider_id}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = "reply-bot"
  }
}

# IAM Policy for DynamoDB access
resource "aws_iam_policy" "cloudrun_dynamodb_access" {
  name        = "reply-bot-cloudrun-dynamodb-${var.environment}"
  description = "Policy for Cloud Run Job Worker to access DynamoDB"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/${var.ddb_table_name}",
          "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/${var.ddb_table_name}/index/*"
        ]
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = "reply-bot"
  }
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "cloudrun_dynamodb_policy" {
  role       = aws_iam_role.cloudrun_workload_identity.name
  policy_arn = aws_iam_policy.cloudrun_dynamodb_access.arn
}

# Output the role ARN for reference
output "aws_workload_identity_role_arn" {
  description = "ARN of the AWS IAM role for Workload Identity"
  value       = aws_iam_role.cloudrun_workload_identity.arn
}

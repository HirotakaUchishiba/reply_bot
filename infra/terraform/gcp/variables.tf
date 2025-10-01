variable "gcp_project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP Region"
  type        = string
  default     = "asia-northeast1"
}

variable "environment" {
  description = "Environment (staging, production)"
  type        = string
  default     = "staging"
}

# AWS configuration for Workload Identity
variable "aws_account_id" {
  description = "AWS Account ID"
  type        = string
}

variable "aws_workload_identity_role_arn" {
  description = "ARN of AWS IAM role for Workload Identity"
  type        = string
}

variable "aws_oidc_provider_id" {
  description = "AWS OIDC Provider ID for Workload Identity"
  type        = string
}

variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "ap-northeast-1"
}

variable "ddb_table_name" {
  description = "DynamoDB table name"
  type        = string
}

variable "auth_token" {
  description = "Authentication token for Cloud Run service"
  type        = string
  sensitive   = true
}

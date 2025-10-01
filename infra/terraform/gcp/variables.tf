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

# AWS credentials for accessing DynamoDB
variable "aws_access_key_id" {
  description = "AWS Access Key ID for DynamoDB access"
  type        = string
  sensitive   = true
}

variable "aws_secret_access_key" {
  description = "AWS Secret Access Key for DynamoDB access"
  type        = string
  sensitive   = true
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

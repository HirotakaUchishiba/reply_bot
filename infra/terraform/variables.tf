variable "aws_region" {
  type        = string
  description = "AWS region to deploy resources into"
  default     = "ap-northeast-1"
}

variable "tf_state_bucket" {
  type        = string
  description = "S3 bucket name for Terraform remote state"
}

variable "tf_state_key_prefix" {
  type        = string
  description = "Key prefix for Terraform state objects"
  default     = "infra/root"
}

variable "tf_state_dynamodb_table" {
  type        = string
  description = "DynamoDB table for Terraform state locking"
}

variable "ddb_table_name" {
  type        = string
  description = "DynamoDB table name for workflow context (default derived from workspace if empty)"
  default     = ""
}

variable "ddb_ttl_attribute" {
  type        = string
  description = "TTL attribute name for DynamoDB items"
  default     = ""
}

variable "sender_email_address" {
  type        = string
  description = "SES sender email address used for replies"
}

variable "slack_channel_id" {
  type        = string
  description = "Slack channel ID for notifications"
  default     = ""
}


variable "async_generation_endpoint" {
  type        = string
  description = "External endpoint to trigger async AI generation (e.g., Cloud Run service)"
  default     = ""
}

variable "async_generation_auth_header" {
  type        = string
  description = "Authorization header value for async generation endpoint"
  default     = ""
}


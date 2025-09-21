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



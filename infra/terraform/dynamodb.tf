resource "aws_dynamodb_table" "context" {
  name         = local.effective_ddb_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "context_id"

  attribute {
    name = "context_id"
    type = "S"
  }

  ttl {
    attribute_name = local.effective_ddb_ttl_attr
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = true
  }
}



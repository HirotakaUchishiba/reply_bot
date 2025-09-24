locals {
  default_ddb_table_name = "reply-bot-context-${terraform.workspace}"
  default_ddb_ttl_attr   = "ttl_epoch"

  effective_ddb_table_name = length(trimspace(var.ddb_table_name)) > 0 ? var.ddb_table_name : local.default_ddb_table_name
  effective_ddb_ttl_attr   = length(trimspace(var.ddb_ttl_attribute)) > 0 ? var.ddb_ttl_attribute : local.default_ddb_ttl_attr
}

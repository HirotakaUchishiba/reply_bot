data "archive_file" "presidio_layer" {
  type        = "zip"
  source_dir  = "${path.root}/../../layers/presidio"
  output_path = "${path.module}/.dist/presidio_layer.zip"
}

resource "aws_lambda_layer_version" "presidio" {
  layer_name          = "reply-bot-presidio-${terraform.workspace}"
  filename            = data.archive_file.presidio_layer.output_path
  source_code_hash    = data.archive_file.presidio_layer.output_base64sha256
  compatible_runtimes = ["python3.11"]
  description         = "Presidio libraries for PII redaction"
}



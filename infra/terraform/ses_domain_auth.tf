# SES Domain Authentication Configuration
# This file contains resources for setting up domain authentication for SES

variable "ses_domain_name" {
  type        = string
  description = "Domain name for SES email sending"
  default     = ""
}

variable "ses_dmarc_email" {
  type        = string
  description = "Email address for DMARC reports"
  default     = ""
}

# SES Domain Identity
resource "aws_ses_domain_identity" "main" {
  count  = var.ses_domain_name != "" ? 1 : 0
  domain = var.ses_domain_name
}

# SES Domain DKIM
resource "aws_ses_domain_dkim" "main" {
  count  = var.ses_domain_name != "" ? 1 : 0
  domain = aws_ses_domain_identity.main[0].domain
}

# Route53 records for domain verification (if using Route53)
# Note: These are commented out as they require Route53 hosted zone
# Uncomment and configure if you're using Route53 for DNS management

# resource "aws_route53_record" "ses_verification" {
#   count   = var.ses_domain_name != "" ? 1 : 0
#   zone_id = var.route53_zone_id
#   name    = "_amazonses.${var.ses_domain_name}"
#   type    = "TXT"
#   ttl     = 600
#   records = [aws_ses_domain_identity.main[0].verification_token]
# }

# resource "aws_route53_record" "ses_dkim" {
#   count   = var.ses_domain_name != "" ? 3 : 0
#   zone_id = var.route53_zone_id
#   name    = "${aws_ses_domain_dkim.main[0].dkim_tokens[count.index]}._domainkey.${var.ses_domain_name}"
#   type    = "CNAME"
#   ttl     = 600
#   records = ["${aws_ses_domain_dkim.main[0].dkim_tokens[count.index]}.dkim.amazonses.com"]
# }

# Outputs for manual DNS configuration
output "ses_domain_verification_token" {
  description = "SES domain verification token for DNS TXT record"
  value       = var.ses_domain_name != "" ? aws_ses_domain_identity.main[0].verification_token : null
}

output "ses_dkim_tokens" {
  description = "SES DKIM tokens for DNS CNAME records"
  value       = var.ses_domain_name != "" ? aws_ses_domain_dkim.main[0].dkim_tokens : null
}

output "ses_domain_identity_arn" {
  description = "SES domain identity ARN"
  value       = var.ses_domain_name != "" ? aws_ses_domain_identity.main[0].arn : null
}

# DNS Configuration Instructions
output "dns_configuration_instructions" {
  description = "Instructions for manual DNS configuration"
  value = var.ses_domain_name != "" ? {
    domain_verification = {
      record_type = "TXT"
      record_name = "_amazonses.${var.ses_domain_name}"
      record_value = aws_ses_domain_identity.main[0].verification_token
    }
    dkim_records = [
      for token in aws_ses_domain_dkim.main[0].dkim_tokens : {
        record_type = "CNAME"
        record_name = "${token}._domainkey.${var.ses_domain_name}"
        record_value = "${token}.dkim.amazonses.com"
      }
    ]
    spf_record = {
      record_type = "TXT"
      record_name = var.ses_domain_name
      record_value = "v=spf1 include:amazonses.com ~all"
    }
    dmarc_record = {
      record_type = "TXT"
      record_name = "_dmarc.${var.ses_domain_name}"
      record_value = var.ses_dmarc_email != "" ? "v=DMARC1; p=none; rua=mailto:${var.ses_dmarc_email}; ruf=mailto:${var.ses_dmarc_email}; fo=1" : "v=DMARC1; p=none; fo=1"
    }
  } : null
}

terraform {
  required_providers { aws = { source = "hashicorp/aws", version = "~> 5.50" } }
}

provider "aws" { region = "eu-central-1" }

resource "aws_kms_key" "creditlens" {
  description         = "CreditLens data and log encryption"
  enable_key_rotation = true
}

resource "aws_s3_bucket" "applications" {
  bucket = "acme-creditlens-applications"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "applications" {
  bucket = aws_s3_bucket.applications.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.creditlens.arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "applications" {
  bucket = aws_s3_bucket.applications.id
  rule {
    id     = "raw-payloads"
    status = "Enabled"
    filter { prefix = "raw/" }
    expiration { days = 30 }
  }
  rule {
    id     = "application-records"
    status = "Enabled"
    filter { prefix = "records/" }
    expiration { days = 1830 }
  }
}

resource "aws_cloudwatch_log_group" "audit" {
  name              = "/creditlens/audit"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.creditlens.arn
}

resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = "creditlens-api"
  stage_name  = "prod"
  method_path = "*/*"
  settings {
    throttling_rate_limit  = 50
    throttling_burst_limit = 100
  }
}

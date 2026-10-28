resource "aws_kms_key" "supportbot" {
  description         = "SupportBot data key"
  enable_key_rotation = true
}

resource "aws_db_instance" "transcripts" {
  identifier                 = "supportbot-transcripts"
  engine                     = "postgres"
  engine_version             = "16.3"
  instance_class             = "db.t4g.medium"
  allocated_storage          = 100
  storage_encrypted          = true
  kms_key_id                 = aws_kms_key.supportbot.arn
  db_subnet_group_name       = "private-data"
  publicly_accessible        = false
  backup_retention_period    = 7
  deletion_protection        = true
  parameter_group_name       = "postgres16-force-ssl"
}

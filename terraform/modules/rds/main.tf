# RDS Module for FFmpeg API

# Generate random password
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# Security Group for RDS
resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-${var.environment}-rds"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-rds-sg"
  })
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier = "${var.project_name}-${var.environment}"

  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.database_config.instance_class

  allocated_storage     = var.database_config.allocated_storage
  max_allocated_storage = var.database_config.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "ffmpeg_api"
  username = "ffmpeg_user"
  password = random_password.db_password.result

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = var.subnet_group_name

  backup_retention_period = var.database_config.backup_retention_days
  backup_window          = "03:00-04:00"
  maintenance_window     = "Sun:04:00-Sun:05:00"

  multi_az               = var.database_config.multi_az
  publicly_accessible    = false
  deletion_protection    = var.database_config.deletion_protection

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  performance_insights_enabled    = true

  skip_final_snapshot = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${var.project_name}-${var.environment}-final-snapshot" : null

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-rds"
  })
}

# CloudWatch Log Groups for RDS
resource "aws_cloudwatch_log_group" "postgresql" {
  name              = "/aws/rds/instance/${aws_db_instance.main.identifier}/postgresql"
  retention_in_days = 7

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-rds-postgresql-logs"
  })
}

resource "aws_cloudwatch_log_group" "upgrade" {
  name              = "/aws/rds/instance/${aws_db_instance.main.identifier}/upgrade"
  retention_in_days = 7

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-rds-upgrade-logs"
  })
}
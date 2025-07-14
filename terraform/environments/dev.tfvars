# Development environment configuration for FFmpeg API

environment = "dev"
aws_region  = "us-west-2"

# VPC Configuration
vpc_cidr = "10.0.0.0/16"
availability_zones = ["us-west-2a", "us-west-2b"]

# EKS Configuration
cluster_version = "1.28"
node_groups = {
  general = {
    instance_types = ["t3.medium"]
    min_size      = 1
    max_size      = 3
    desired_size  = 1
    capacity_type = "ON_DEMAND"
    labels = {
      role = "general"
    }
    taints = []
  }
  workers = {
    instance_types = ["c5.large"]
    min_size      = 0
    max_size      = 5
    desired_size  = 0
    capacity_type = "SPOT"
    labels = {
      role = "worker"
    }
    taints = [{
      key    = "workload"
      value  = "processing"
      effect = "NO_SCHEDULE"
    }]
  }
}

# Database Configuration
database_config = {
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  max_allocated_storage = 50
  backup_retention_days = 3
  multi_az         = false
  deletion_protection = false
}

# Redis Configuration
redis_config = {
  node_type          = "cache.t3.micro"
  num_cache_nodes    = 1
  parameter_group    = "default.redis7"
  port              = 6379
}

# S3 Configuration
s3_config = {
  versioning_enabled = true
  lifecycle_enabled  = true
  transition_days    = 30
  expiration_days    = 90
}

# Monitoring Configuration
monitoring_config = {
  enable_prometheus     = true
  enable_grafana       = true
  enable_elasticsearch = false  # Disabled for dev to save costs
  retention_days       = 7
}

# Security Configuration
security_config = {
  enable_waf           = false  # Disabled for dev
  enable_secrets_manager = true
  kms_key_rotation     = false
}

# Additional tags
tags = {
  Owner       = "dev-team"
  CostCenter  = "development"
  Backup      = "daily"
}
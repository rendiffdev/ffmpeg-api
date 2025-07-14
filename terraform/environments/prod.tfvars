# Production environment configuration for FFmpeg API

environment = "prod"
aws_region  = "us-west-2"

# VPC Configuration
vpc_cidr = "10.0.0.0/16"
availability_zones = ["us-west-2a", "us-west-2b", "us-west-2c"]

# EKS Configuration
cluster_version = "1.28"
node_groups = {
  general = {
    instance_types = ["t3.large", "t3.xlarge"]
    min_size      = 2
    max_size      = 10
    desired_size  = 3
    capacity_type = "ON_DEMAND"
    labels = {
      role = "general"
    }
    taints = []
  }
  workers = {
    instance_types = ["c5.xlarge", "c5.2xlarge"]
    min_size      = 1
    max_size      = 50
    desired_size  = 3
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
  gpu_workers = {
    instance_types = ["g4dn.xlarge", "g4dn.2xlarge"]
    min_size      = 0
    max_size      = 10
    desired_size  = 0
    capacity_type = "ON_DEMAND"
    labels = {
      role = "gpu-worker"
      "node.kubernetes.io/accelerator" = "nvidia-tesla-t4"
    }
    taints = [{
      key    = "workload"
      value  = "gpu-processing"
      effect = "NO_SCHEDULE"
    }]
  }
}

# Database Configuration
database_config = {
  instance_class    = "db.r6g.large"
  allocated_storage = 100
  max_allocated_storage = 1000
  backup_retention_days = 30
  multi_az         = true
  deletion_protection = true
}

# Redis Configuration
redis_config = {
  node_type          = "cache.r6g.large"
  num_cache_nodes    = 2
  parameter_group    = "default.redis7"
  port              = 6379
}

# S3 Configuration
s3_config = {
  versioning_enabled = true
  lifecycle_enabled  = true
  transition_days    = 30
  expiration_days    = 2555  # 7 years
}

# Monitoring Configuration
monitoring_config = {
  enable_prometheus     = true
  enable_grafana       = true
  enable_elasticsearch = true
  retention_days       = 90
}

# Security Configuration
security_config = {
  enable_waf           = true
  enable_secrets_manager = true
  kms_key_rotation     = true
}

# Domain and SSL
domain_name = "api.ffmpeg.example.com"
# certificate_arn = "arn:aws:acm:us-west-2:123456789012:certificate/..."

# Additional tags
tags = {
  Owner       = "platform-team"
  CostCenter  = "production"
  Backup      = "continuous"
  Compliance  = "required"
}
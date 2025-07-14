# Global variables for FFmpeg API infrastructure

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "ffmpeg-api"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-west-2a", "us-west-2b", "us-west-2c"]
}

variable "cluster_version" {
  description = "Kubernetes cluster version"
  type        = string
  default     = "1.28"
}

variable "node_groups" {
  description = "EKS node group configurations"
  type = map(object({
    instance_types = list(string)
    min_size      = number
    max_size      = number
    desired_size  = number
    capacity_type = string
    labels        = map(string)
    taints        = list(object({
      key    = string
      value  = string
      effect = string
    }))
  }))
  default = {
    general = {
      instance_types = ["t3.medium", "t3.large"]
      min_size      = 1
      max_size      = 10
      desired_size  = 2
      capacity_type = "ON_DEMAND"
      labels = {
        role = "general"
      }
      taints = []
    }
    workers = {
      instance_types = ["c5.xlarge", "c5.2xlarge"]
      min_size      = 0
      max_size      = 20
      desired_size  = 1
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
}

variable "database_config" {
  description = "RDS database configuration"
  type = object({
    instance_class    = string
    allocated_storage = number
    max_allocated_storage = number
    backup_retention_days = number
    multi_az         = bool
    deletion_protection = bool
  })
  default = {
    instance_class    = "db.t3.micro"
    allocated_storage = 20
    max_allocated_storage = 100
    backup_retention_days = 7
    multi_az         = false
    deletion_protection = false
  }
}

variable "redis_config" {
  description = "ElastiCache Redis configuration"
  type = object({
    node_type          = string
    num_cache_nodes    = number
    parameter_group    = string
    port              = number
  })
  default = {
    node_type          = "cache.t3.micro"
    num_cache_nodes    = 1
    parameter_group    = "default.redis7"
    port              = 6379
  }
}

variable "s3_config" {
  description = "S3 bucket configuration"
  type = object({
    versioning_enabled = bool
    lifecycle_enabled  = bool
    transition_days    = number
    expiration_days    = number
  })
  default = {
    versioning_enabled = true
    lifecycle_enabled  = true
    transition_days    = 30
    expiration_days    = 365
  }
}

variable "monitoring_config" {
  description = "Monitoring configuration"
  type = object({
    enable_prometheus     = bool
    enable_grafana       = bool
    enable_elasticsearch = bool
    retention_days       = number
  })
  default = {
    enable_prometheus     = true
    enable_grafana       = true
    enable_elasticsearch = true
    retention_days       = 30
  }
}

variable "security_config" {
  description = "Security configuration"
  type = object({
    enable_waf           = bool
    enable_secrets_manager = bool
    kms_key_rotation     = bool
  })
  default = {
    enable_waf           = true
    enable_secrets_manager = true
    kms_key_rotation     = true
  }
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}
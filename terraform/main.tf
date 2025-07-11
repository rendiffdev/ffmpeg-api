# Main Terraform configuration for FFmpeg API infrastructure

locals {
  common_tags = merge(var.tags, {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  })
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# VPC and Networking
module "vpc" {
  source = "./modules/vpc"
  
  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr          = var.vpc_cidr
  availability_zones = var.availability_zones
  
  tags = local.common_tags
}

# EKS Cluster
module "eks" {
  source = "./modules/eks"
  
  project_name     = var.project_name
  environment      = var.environment
  cluster_version  = var.cluster_version
  
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnet_ids
  node_groups     = var.node_groups
  
  tags = local.common_tags
}

# RDS Database
module "rds" {
  source = "./modules/rds"
  
  project_name    = var.project_name
  environment     = var.environment
  
  vpc_id         = module.vpc.vpc_id
  subnet_ids     = module.vpc.database_subnet_ids
  security_group_ids = [module.eks.cluster_security_group_id]
  
  database_config = var.database_config
  
  tags = local.common_tags
}

# ElastiCache Redis
module "redis" {
  source = "./modules/redis"
  
  project_name    = var.project_name
  environment     = var.environment
  
  vpc_id         = module.vpc.vpc_id
  subnet_ids     = module.vpc.private_subnet_ids
  security_group_ids = [module.eks.cluster_security_group_id]
  
  redis_config = var.redis_config
  
  tags = local.common_tags
}

# S3 Storage
module "s3" {
  source = "./modules/s3"
  
  project_name = var.project_name
  environment  = var.environment
  
  s3_config = var.s3_config
  
  tags = local.common_tags
}

# Secrets Manager
module "secrets" {
  source = "./modules/secrets"
  
  project_name = var.project_name
  environment  = var.environment
  
  database_endpoint = module.rds.endpoint
  database_password = module.rds.password
  redis_endpoint    = module.redis.endpoint
  
  tags = local.common_tags
}

# IAM Roles and Policies
module "iam" {
  source = "./modules/iam"
  
  project_name    = var.project_name
  environment     = var.environment
  
  eks_cluster_name = module.eks.cluster_name
  s3_bucket_arn   = module.s3.bucket_arn
  secrets_arn     = module.secrets.secret_arn
  
  tags = local.common_tags
}

# Application Load Balancer
module "alb" {
  source = "./modules/alb"
  
  project_name = var.project_name
  environment  = var.environment
  
  vpc_id         = module.vpc.vpc_id
  subnet_ids     = module.vpc.public_subnet_ids
  certificate_arn = var.certificate_arn
  
  tags = local.common_tags
}

# WAF (if enabled)
module "waf" {
  source = "./modules/waf"
  count  = var.security_config.enable_waf ? 1 : 0
  
  project_name = var.project_name
  environment  = var.environment
  
  alb_arn = module.alb.arn
  
  tags = local.common_tags
}

# Monitoring (if enabled)
module "monitoring" {
  source = "./modules/monitoring"
  count  = var.monitoring_config.enable_prometheus ? 1 : 0
  
  project_name = var.project_name
  environment  = var.environment
  
  cluster_name = module.eks.cluster_name
  vpc_id       = module.vpc.vpc_id
  
  monitoring_config = var.monitoring_config
  
  tags = local.common_tags
}
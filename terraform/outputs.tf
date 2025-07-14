# Terraform outputs for FFmpeg API infrastructure

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = module.vpc.vpc_cidr
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.vpc.private_subnet_ids
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.vpc.public_subnet_ids
}

output "database_subnet_ids" {
  description = "IDs of the database subnets"
  value       = module.vpc.database_subnet_ids
}

output "eks_cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "Endpoint of the EKS cluster"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "eks_cluster_iam_role_arn" {
  description = "IAM role ARN associated with the EKS cluster"
  value       = module.eks.cluster_iam_role_arn
}

output "eks_node_groups" {
  description = "EKS node groups"
  value       = module.eks.node_groups
}

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = module.rds.endpoint
  sensitive   = true
}

output "rds_port" {
  description = "RDS instance port"
  value       = module.rds.port
}

output "rds_database_name" {
  description = "RDS database name"
  value       = module.rds.database_name
}

output "redis_endpoint" {
  description = "Redis cluster endpoint"
  value       = module.redis.endpoint
  sensitive   = true
}

output "redis_port" {
  description = "Redis cluster port"
  value       = module.redis.port
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = module.s3.bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = module.s3.bucket_arn
}

output "s3_bucket_domain_name" {
  description = "Domain name of the S3 bucket"
  value       = module.s3.bucket_domain_name
}

output "secrets_manager_arn" {
  description = "ARN of the secrets manager secret"
  value       = module.secrets.secret_arn
  sensitive   = true
}

output "application_role_arn" {
  description = "ARN of the application IAM role"
  value       = module.iam.application_role_arn
}

output "worker_role_arn" {
  description = "ARN of the worker IAM role"
  value       = module.iam.worker_role_arn
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.alb.dns_name
}

output "alb_zone_id" {
  description = "Zone ID of the Application Load Balancer"
  value       = module.alb.zone_id
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = module.alb.arn
}

output "waf_web_acl_arn" {
  description = "ARN of the WAF Web ACL"
  value       = var.security_config.enable_waf ? module.waf[0].web_acl_arn : null
}

output "kubeconfig_command" {
  description = "Command to update kubeconfig"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "environment_variables" {
  description = "Environment variables for the application"
  value = {
    AWS_REGION           = var.aws_region
    DATABASE_URL         = "postgresql://ffmpeg_user:${module.rds.password}@${module.rds.endpoint}:${module.rds.port}/${module.rds.database_name}"
    REDIS_URL           = "redis://${module.redis.endpoint}:${module.redis.port}"
    S3_BUCKET_NAME      = module.s3.bucket_name
    SECRETS_MANAGER_ARN = module.secrets.secret_arn
    ENVIRONMENT         = var.environment
  }
  sensitive = true
}
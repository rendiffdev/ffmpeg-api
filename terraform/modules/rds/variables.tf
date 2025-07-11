variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs"
  type        = list(string)
}

variable "subnet_group_name" {
  description = "Name of the DB subnet group"
  type        = string
  default     = ""
}

variable "security_group_ids" {
  description = "List of security group IDs that can access RDS"
  type        = list(string)
  default     = []
}

variable "database_config" {
  description = "Database configuration"
  type = object({
    instance_class    = string
    allocated_storage = number
    max_allocated_storage = number
    backup_retention_days = number
    multi_az         = bool
    deletion_protection = bool
  })
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
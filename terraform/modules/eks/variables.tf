variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes cluster version"
  type        = string
  default     = "1.28"
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs"
  type        = list(string)
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
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
output "endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.main.endpoint
}

output "port" {
  description = "RDS instance port"
  value       = aws_db_instance.main.port
}

output "database_name" {
  description = "RDS database name"
  value       = aws_db_instance.main.db_name
}

output "username" {
  description = "RDS database username"
  value       = aws_db_instance.main.username
}

output "password" {
  description = "RDS database password"
  value       = random_password.db_password.result
  sensitive   = true
}

output "security_group_id" {
  description = "Security group ID of RDS instance"
  value       = aws_security_group.rds.id
}
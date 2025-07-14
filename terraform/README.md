# FFmpeg API - Infrastructure as Code

This directory contains Terraform/OpenTofu infrastructure code for deploying the FFmpeg API platform on AWS with Kubernetes (EKS).

## 🏗️ Architecture Overview

The infrastructure includes:

- **VPC**: Multi-AZ network with public, private, and database subnets
- **EKS Cluster**: Kubernetes cluster with multiple node groups
- **RDS PostgreSQL**: Managed database with backup and encryption
- **ElastiCache Redis**: In-memory cache for performance
- **S3**: Object storage for media files
- **ALB**: Application Load Balancer with SSL termination
- **WAF**: Web Application Firewall for security
- **Secrets Manager**: Secure credential storage
- **CloudWatch**: Comprehensive monitoring and logging

## 📁 Directory Structure

```
terraform/
├── main.tf                    # Main infrastructure configuration
├── variables.tf               # Input variables
├── outputs.tf                 # Output values
├── versions.tf                # Provider requirements
├── modules/                   # Reusable Terraform modules
│   ├── vpc/                   # VPC and networking
│   ├── eks/                   # EKS cluster
│   ├── rds/                   # PostgreSQL database
│   ├── redis/                 # ElastiCache Redis
│   ├── s3/                    # S3 storage
│   ├── iam/                   # IAM roles and policies
│   ├── alb/                   # Application Load Balancer
│   ├── waf/                   # Web Application Firewall
│   ├── secrets/               # AWS Secrets Manager
│   └── monitoring/            # CloudWatch and monitoring
└── environments/              # Environment-specific configurations
    ├── dev.tfvars             # Development environment
    ├── staging.tfvars         # Staging environment
    └── prod.tfvars            # Production environment
```

## 🚀 Quick Start

### Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **Terraform** >= 1.0 or **OpenTofu** >= 1.6
3. **kubectl** for Kubernetes management
4. **Helm** for application deployment

### Environment Setup

1. **Configure AWS credentials:**
```bash
aws configure
# or use AWS IAM roles for production
```

2. **Initialize Terraform backend:**
```bash
# Create S3 bucket for state storage
aws s3 mb s3://your-terraform-state-bucket

# Create DynamoDB table for state locking
aws dynamodb create-table \
    --table-name terraform-locks \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
```

3. **Update backend configuration:**
```bash
# Edit terraform/versions.tf to add your S3 bucket
terraform {
  backend "s3" {
    bucket         = "your-terraform-state-bucket"
    key            = "ffmpeg-api/dev/terraform.tfstate"
    region         = "us-west-2"
    dynamodb_table = "terraform-locks"
  }
}
```

### Deployment

1. **Initialize Terraform:**
```bash
cd terraform
terraform init
```

2. **Plan deployment:**
```bash
# For development environment
terraform plan -var-file="environments/dev.tfvars"

# For production environment
terraform plan -var-file="environments/prod.tfvars"
```

3. **Apply infrastructure:**
```bash
# Deploy development environment
terraform apply -var-file="environments/dev.tfvars"

# Deploy production environment
terraform apply -var-file="environments/prod.tfvars"
```

4. **Configure kubectl:**
```bash
aws eks update-kubeconfig --region us-west-2 --name ffmpeg-api-dev
```

## 🔧 Configuration

### Environment Variables

Key variables that can be customized in `environments/*.tfvars`:

| Variable | Description | Default |
|----------|-------------|---------|
| `environment` | Environment name (dev/staging/prod) | - |
| `aws_region` | AWS region | us-west-2 |
| `vpc_cidr` | VPC CIDR block | 10.0.0.0/16 |
| `cluster_version` | Kubernetes version | 1.28 |
| `node_groups` | EKS node group configurations | See values |
| `database_config` | RDS configuration | See values |
| `redis_config` | ElastiCache configuration | See values |

### Node Groups

The infrastructure supports multiple node groups:

- **General**: For API workloads (t3.medium - t3.xlarge)
- **Workers**: For processing workloads (c5.large - c5.2xlarge)
- **GPU Workers**: For GPU-accelerated processing (g4dn.xlarge+)

### Security Features

- **Encryption at rest** for all data stores
- **VPC endpoints** for AWS services
- **Security groups** with least privilege
- **IAM roles** with fine-grained permissions
- **KMS keys** for encryption
- **WAF** for application protection

## 🔐 Security Considerations

### Secrets Management

Sensitive values are managed through:

1. **AWS Secrets Manager** for database passwords
2. **Kubernetes Secrets** for application configuration
3. **IAM roles** for service authentication
4. **KMS** for encryption keys

### Network Security

- Private subnets for worker nodes
- Database subnets isolated from internet
- Security groups with minimal required access
- VPC endpoints for AWS service communication

### Access Control

- **RBAC** configured for Kubernetes
- **IAM roles** for service accounts
- **Pod security contexts** with non-root users
- **Network policies** for inter-pod communication

## 📊 Monitoring

### CloudWatch Integration

- **EKS cluster logging** enabled
- **RDS performance insights** enabled
- **Custom metrics** from application
- **Automated alarms** for critical metrics

### Cost Optimization

- **Spot instances** for worker nodes
- **Automated scaling** based on workload
- **Lifecycle policies** for S3 storage
- **Reserved instances** for production

## 🚨 Disaster Recovery

### Backup Strategy

- **RDS automated backups** (7-30 days retention)
- **EBS snapshots** for persistent volumes
- **S3 versioning** for object storage
- **Multi-AZ deployment** for high availability

### Recovery Procedures

1. **Database recovery** from RDS snapshots
2. **Application recovery** via Kubernetes deployments
3. **Storage recovery** from S3 versioning
4. **Full environment recreation** from Terraform

## 🔄 CI/CD Integration

### GitHub Actions

The infrastructure includes automated CI/CD pipelines:

- **Plan on PR** - Shows infrastructure changes
- **Apply on merge** - Deploys to development
- **Manual approval** - Required for production
- **Security scanning** - Vulnerability detection

### Deployment Flow

1. **Pull Request** → Terraform plan
2. **Merge to main** → Deploy to dev
3. **Manual trigger** → Deploy to staging/prod
4. **Rollback** → Previous Terraform state

## 🛠️ Maintenance

### Regular Tasks

1. **Update Kubernetes versions** quarterly
2. **Patch worker nodes** monthly
3. **Review security groups** quarterly
4. **Update Terraform modules** regularly

### Monitoring Tasks

1. **Check CloudWatch alarms** daily
2. **Review cost reports** weekly
3. **Security audit** monthly
4. **Disaster recovery test** quarterly

## 📞 Troubleshooting

### Common Issues

1. **EKS node not ready**
   ```bash
   kubectl describe nodes
   kubectl get pods -n kube-system
   ```

2. **RDS connection issues**
   ```bash
   # Check security groups
   aws ec2 describe-security-groups --group-ids sg-xxxxx
   ```

3. **S3 access denied**
   ```bash
   # Check IAM policies
   aws iam get-role-policy --role-name xxx --policy-name xxx
   ```

### Debugging Commands

```bash
# Check Terraform state
terraform show

# Validate configuration
terraform validate

# Check EKS cluster
aws eks describe-cluster --name ffmpeg-api-dev

# Check RDS instance
aws rds describe-db-instances

# Check S3 bucket
aws s3 ls s3://ffmpeg-api-storage-dev
```

## 🔗 Related Documentation

- [Kubernetes Manifests](../k8s/README.md)
- [Helm Charts](../helm/README.md)
- [Application Documentation](../docs/)
- [Monitoring Guide](../docs/monitoring-guide.md)

## 🤝 Contributing

1. **Create feature branch** from main
2. **Update Terraform code** with proper formatting
3. **Test in development** environment
4. **Submit pull request** with plan output
5. **Get approval** before merging

## 📋 Terraform/OpenTofu Compatibility

This infrastructure is compatible with both Terraform and OpenTofu:

```bash
# Using Terraform
terraform init && terraform plan

# Using OpenTofu
tofu init && tofu plan
```

All configurations use standard HCL syntax and are tested with both tools.

---

**Support**: For infrastructure issues, contact the DevOps team or create an issue in the repository.
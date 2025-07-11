# FFmpeg API - Kubernetes Manifests

This directory contains Kubernetes manifests for deploying the FFmpeg API platform on any Kubernetes cluster.

## 📁 Directory Structure

```
k8s/
├── base/                      # Base Kubernetes manifests
│   ├── namespace.yaml         # Namespaces
│   ├── configmap.yaml         # Configuration
│   ├── secret.yaml            # Secrets (template)
│   ├── rbac.yaml              # RBAC configuration
│   ├── api-deployment.yaml    # API deployment
│   ├── worker-deployment.yaml # Worker deployments
│   ├── services.yaml          # Kubernetes services
│   ├── ingress.yaml           # Ingress configuration
│   └── hpa.yaml               # Horizontal Pod Autoscaler
└── overlays/                  # Environment-specific overlays
    ├── dev/
    ├── staging/
    └── prod/
```

## 🚀 Quick Deployment

### Prerequisites

- Kubernetes cluster (>= 1.24)
- kubectl configured
- Ingress controller (ALB, NGINX, etc.)
- Container registry access

### Basic Deployment

1. **Apply namespaces:**
```bash
kubectl apply -f base/namespace.yaml
```

2. **Configure secrets:**
```bash
# Edit base/secret.yaml with your values
kubectl apply -f base/secret.yaml
```

3. **Deploy application:**
```bash
kubectl apply -f base/
```

4. **Check deployment:**
```bash
kubectl get pods -n ffmpeg-api
kubectl get services -n ffmpeg-api
kubectl get ingress -n ffmpeg-api
```

## 🔧 Configuration

### Environment Variables

Key configuration in `configmap.yaml`:

```yaml
# Application settings
ENVIRONMENT: "production"
LOG_LEVEL: "INFO"
API_WORKERS: "4"

# Processing settings
MAX_CONCURRENT_JOBS: "10"
MAX_FILE_SIZE: "1073741824"  # 1GB

# Cache settings
CACHE_TTL: "3600"
CACHE_TYPE: "redis"
```

### Secrets

Required secrets in `secret.yaml`:

```yaml
# Database
DATABASE_URL: "postgresql://..."
DATABASE_PASSWORD: "..."

# Redis
REDIS_URL: "redis://..."

# Storage
S3_BUCKET_NAME: "..."
AWS_ACCESS_KEY_ID: "..."
AWS_SECRET_ACCESS_KEY: "..."

# Application
SECRET_KEY: "..."
JWT_SECRET: "..."
```

### Resource Requirements

#### API Pods
- **Requests**: 250m CPU, 512Mi memory
- **Limits**: 500m CPU, 1Gi memory
- **Replicas**: 3 (autoscaled 2-20)

#### Worker Pods
- **CPU Workers**: 500m-2000m CPU, 1-4Gi memory
- **GPU Workers**: 1000m-4000m CPU, 2-8Gi memory + 1 GPU
- **Replicas**: Autoscaled based on queue depth

## 🔄 Autoscaling

### Horizontal Pod Autoscaler (HPA)

API autoscaling triggers:
- CPU utilization > 70%
- Memory utilization > 80%
- Requests per second > 100

Worker autoscaling triggers:
- CPU utilization > 80%
- Memory utilization > 85%
- Queue depth > 10 jobs

### Vertical Pod Autoscaler (VPA)

```bash
# Install VPA (if not available)
kubectl apply -f https://github.com/kubernetes/autoscaler/releases/download/vertical-pod-autoscaler-0.13.0/vpa-release-0.13.0.yaml

# Apply VPA configuration
kubectl apply -f vpa.yaml
```

## 🔐 Security

### Pod Security

- **Non-root user** (UID 1000)
- **Read-only root filesystem**
- **No privilege escalation**
- **Dropped capabilities**

### Network Security

- **Network policies** for pod-to-pod communication
- **Service mesh** integration (Istio/Linkerd)
- **TLS encryption** for all communications

### RBAC Configuration

Minimal permissions:
- Read ConfigMaps and Secrets
- Access to own namespace only
- Metrics endpoint access
- Event creation for logging

## 📊 Monitoring

### Prometheus Integration

Automatic metrics collection:
```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "9000"
  prometheus.io/path: "/metrics"
```

### Health Checks

#### Liveness Probe
- **Path**: `/health`
- **Initial delay**: 30s
- **Period**: 10s
- **Timeout**: 5s

#### Readiness Probe
- **Path**: `/ready`
- **Initial delay**: 5s
- **Period**: 5s
- **Timeout**: 3s

#### Startup Probe
- **Path**: `/health`
- **Failure threshold**: 30
- **Period**: 10s

## 🗄️ Storage

### Persistent Volumes

```yaml
# Shared storage for uploads
- name: uploads
  emptyDir:
    sizeLimit: 10Gi

# Processing workspace
- name: processing
  emptyDir:
    sizeLimit: 50Gi

# Long-term storage (optional)
- name: storage
  persistentVolumeClaim:
    claimName: ffmpeg-api-storage
```

### Storage Classes

Recommended storage classes:
- **gp3** (AWS EBS) for general use
- **io1/io2** (AWS EBS) for high IOPS
- **efs** (AWS EFS) for shared storage

## 🌐 Ingress Configuration

### AWS Load Balancer Controller

```yaml
annotations:
  kubernetes.io/ingress.class: alb
  alb.ingress.kubernetes.io/scheme: internet-facing
  alb.ingress.kubernetes.io/target-type: ip
  alb.ingress.kubernetes.io/healthcheck-path: /health
  alb.ingress.kubernetes.io/ssl-redirect: "443"
```

### NGINX Ingress

```yaml
annotations:
  kubernetes.io/ingress.class: nginx
  nginx.ingress.kubernetes.io/proxy-body-size: "1g"
  nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
  nginx.ingress.kubernetes.io/rate-limit: "100"
```

## 🚨 Troubleshooting

### Common Issues

1. **Pods not starting:**
```bash
kubectl describe pod <pod-name> -n ffmpeg-api
kubectl logs <pod-name> -n ffmpeg-api
```

2. **Service not accessible:**
```bash
kubectl get endpoints -n ffmpeg-api
kubectl describe service ffmpeg-api-service -n ffmpeg-api
```

3. **Ingress not working:**
```bash
kubectl describe ingress ffmpeg-api-ingress -n ffmpeg-api
kubectl get events -n ffmpeg-api
```

### Debug Commands

```bash
# Check all resources
kubectl get all -n ffmpeg-api

# Check pod logs
kubectl logs -f deployment/ffmpeg-api -n ffmpeg-api

# Check resource usage
kubectl top pods -n ffmpeg-api
kubectl top nodes

# Port forward for testing
kubectl port-forward service/ffmpeg-api-service 8080:8000 -n ffmpeg-api
```

### Performance Issues

1. **High CPU usage:**
   - Check HPA scaling
   - Review resource limits
   - Analyze application metrics

2. **Memory leaks:**
   - Monitor pod restart count
   - Check application logs
   - Review garbage collection

3. **Slow responses:**
   - Check Redis connectivity
   - Review database performance
   - Analyze network latency

## 🔧 Customization

### Environment-Specific Changes

Create overlays for different environments:

```bash
k8s/overlays/dev/
├── kustomization.yaml
├── replica-count.yaml
└── resource-limits.yaml
```

### Custom Resources

Add custom resources as needed:
- ServiceMonitor for Prometheus
- VirtualService for Istio
- IngressRoute for Traefik

## 📋 Maintenance

### Regular Tasks

1. **Update container images** regularly
2. **Review resource usage** weekly
3. **Check security policies** monthly
4. **Update Kubernetes** quarterly

### Backup Procedures

1. **ConfigMaps and Secrets** backup
2. **Persistent volume** snapshots
3. **Application data** export
4. **RBAC configuration** backup

## 🔗 Integration

### External Secrets Operator

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: ffmpeg-api-secrets
spec:
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: ffmpeg-api-secrets
```

### Service Mesh

Integration with service mesh:
- **Istio**: Automatic sidecar injection
- **Linkerd**: Traffic policies
- **Consul Connect**: Service discovery

---

**Support**: For Kubernetes deployment issues, check logs and events first, then contact the platform team.
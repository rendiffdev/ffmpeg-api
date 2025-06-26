# Rendiff Installation Guide

This guide covers various installation methods for the Rendiff FFmpeg API service.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start with Setup Wizard](#quick-start-with-setup-wizard)
3. [Production Deployment](#production-deployment)
4. [Manual Installation](#manual-installation)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Updates & Maintenance](#updates-maintenance)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 20.04+, RHEL 8+, Debian 11+)
- **CPU**: 4+ cores recommended
- **RAM**: 8GB minimum, 16GB+ recommended
- **Storage**: 100GB+ available space
- **Network**: Stable internet connection for pulling images

### Software Requirements

- Docker 20.10+ and Docker Compose 2.0+
- Git
- Python 3.12+ (for manual installation)

> **Note**: PostgreSQL is no longer required! Rendiff now uses SQLite as the default database, which is automatically managed within the application. No external database setup is needed.

## Quick Start with Setup Wizard

The fastest and easiest way to get Rendiff running:

### Step 1: Clone Repository

```bash
git clone https://github.com/rendiffdev/ffmpeg-api.git
cd ffmpeg-api
```

### Step 2: Run Setup Wizard

```bash
# Run the interactive setup wizard
docker-compose run --rm setup
```

The setup wizard will guide you through:

1. **Deployment Configuration**
   - Choose deployment type (Docker, Kubernetes, Manual)
   - Select deployment profile (Minimal, Standard, Full)

2. **API Configuration**
   - API bind address and port
   - Number of workers
   - External URL for webhooks

3. **Storage Configuration**
   - Configure storage backends:
     - Local filesystem
     - Network storage (NFS, SMB)
     - Cloud storage (S3, Azure, GCS, MinIO)
   - Set input/output policies
   - Choose default backend

4. **Security Settings**
   - Enable/disable API key authentication
   - Generate secure API keys
   - Configure IP whitelisting (optional)

5. **Resource Limits**
   - Maximum file size
   - Concurrent job limits
   - CPU/GPU worker configuration

6. **Advanced Options** (optional)
   - External database configuration
   - Monitoring setup (Prometheus/Grafana)
   - Webhook settings

### Step 3: Start Services

After completing the wizard:

```bash
# Start all configured services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### Step 4: Verify Installation

```bash
# Check API health
curl http://localhost:8080/api/v1/health

# Test with your API key (shown during setup)
curl -H "X-API-Key: your-api-key" http://localhost:8080/api/v1/capabilities
```

## Production Deployment

### Automated Installation

For production servers, use our installation script:

```bash
# Download and run installer
curl -sSL https://raw.githubusercontent.com/rendiffdev/ffmpeg-api/main/scripts/install.sh | sudo bash

# Then run the setup wizard
cd /opt/rendiff
docker-compose run --rm setup
```

### Storage Backend Examples

#### Local Storage
```yaml
backends:
  local:
    type: filesystem
    base_path: /mnt/fast-storage/rendiff
    permissions: "0755"
```

#### NFS Storage
```yaml
backends:
  nfs:
    type: network
    protocol: nfs
    server: storage.company.internal
    export: /media/rendiff
    mount_options: "rw,sync,hard,intr"
```

#### S3/MinIO Storage
```yaml
backends:
  s3:
    type: s3
    endpoint: https://s3.amazonaws.com
    region: us-east-1
    bucket: rendiff-media
    access_key: ${S3_ACCESS_KEY}
    secret_key: ${S3_SECRET_KEY}
```

#### Azure Blob Storage
```yaml
backends:
  azure:
    type: azure
    account_name: rendiffmedia
    container: videos
    account_key: ${AZURE_KEY}
```

## Manual Installation

For custom deployments without Docker:

### 1. Install Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y \
    python3.12 python3.12-venv \
    ffmpeg \
    postgresql-14 \
    redis-server \
    nginx

# RHEL/CentOS
sudo yum install -y \
    python3.12 \
    ffmpeg \
    postgresql14-server \
    redis \
    nginx
```

### 2. Create Python Environment

```bash
python3.12 -m venv /opt/rendiff/venv
source /opt/rendiff/venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Services

Run the setup wizard in manual mode:

```bash
python setup/wizard.py --mode manual
```

### 4. Start Services

```bash
# Start API
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Start workers
celery -A worker.main worker --loglevel=info

# Start with systemd (recommended)
sudo systemctl start rendiff-api
sudo systemctl start rendiff-worker
```

## Kubernetes Deployment

### Using Helm

```bash
# Add Rendiff Helm repository
helm repo add rendiff https://charts.rendiff.dev
helm repo update

# Run setup wizard to generate values
docker run --rm -it rendiff/setup:latest --mode k8s > values.yaml

# Install with generated values
helm install rendiff rendiff/rendiff -f values.yaml
```

### Manual Kubernetes Setup

```bash
# Generate Kubernetes manifests
docker-compose run --rm setup --mode k8s --output k8s/

# Apply manifests
kubectl create namespace rendiff
kubectl apply -f k8s/
```

## Updates & Maintenance

### Checking for Updates

```bash
# Check for available updates
./scripts/updater.py check

# Check specific components
./scripts/updater.py check --components docker database
```

### Performing Updates

```bash
# Update to latest stable version
./scripts/updater.py update

# Update to specific version
./scripts/updater.py update --version 1.2.0

# Update specific components only
./scripts/updater.py update --components docker

# Skip backup (not recommended)
./scripts/updater.py update --skip-backup
```

### Backup Management

```bash
# Create manual backup
./scripts/updater.py backup

# List backups
./scripts/updater.py list-backups

# Restore from backup
./scripts/updater.py restore backup_20250127_120000

# Clean old backups (keep last 5)
./scripts/updater.py cleanup --keep 5
```

### System Verification

```bash
# Verify system integrity
./scripts/updater.py verify

# Attempt automatic repair
./scripts/updater.py repair
```

## Troubleshooting

### Common Issues

#### 1. Setup Wizard Connection Issues

If the wizard can't connect to storage backends:

```bash
# Test S3 connection manually
aws s3 ls s3://your-bucket --endpoint-url https://your-endpoint

# Test NFS mount
sudo mount -t nfs server:/export /mnt/test

# Check firewall rules
sudo iptables -L
```

#### 2. Docker Permission Errors

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Fix storage permissions
sudo chown -R $(id -u):$(id -g) ./storage
chmod -R 755 ./storage
```

#### 3. Service Won't Start

```bash
# Check logs
docker-compose logs api
docker-compose logs worker-cpu

# Verify configuration
docker-compose config

# Rebuild if needed
docker-compose build --no-cache
```

#### 4. Database Connection Failed

```bash
# For SQLite, check if database file exists
ls -la data/rendiff.db

# Reset database
rm -f data/rendiff.db
# Database will be recreated on next startup

# Initialize database manually if needed
python scripts/init-sqlite.py
```

### Getting Help

- Check logs: `docker-compose logs -f`
- API documentation: http://localhost:8080/docs
- Run diagnostics: `./scripts/updater.py verify`
- GitHub Issues: https://github.com/rendiffdev/ffmpeg-api/issues

## Next Steps

1. Test your installation with a simple conversion
2. Configure additional storage backends as needed
3. Set up monitoring dashboards (if enabled)
4. Review security settings and API keys
5. Configure backups and retention policies

## Production Deployment

### 1. Automated Installation Script

For production servers, use our installation script:

```bash
# Download and run installer
curl -sSL https://raw.githubusercontent.com/rendiffdev/ffmpeg-api/main/scripts/install.sh | sudo bash

# Or download first and review
wget https://raw.githubusercontent.com/rendiffdev/ffmpeg-api/main/scripts/install.sh
chmod +x install.sh
sudo ./install.sh
```

The script will:
- Install all dependencies
- Set up systemd service
- Configure storage directories
- Initialize the database
- Start the services

### 2. Manual Production Setup

#### Step 1: Create dedicated user

```bash
sudo useradd -r -s /bin/bash -m -d /var/lib/rendiff rendiff
```

#### Step 2: Install dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    docker.io \
    docker-compose \
    postgresql-client \
    ffmpeg \
    git \
    curl

# Add rendiff user to docker group
sudo usermod -aG docker rendiff
```

#### Step 3: Set up directories

```bash
# Create directories
sudo mkdir -p /opt/rendiff
sudo mkdir -p /var/lib/rendiff/{storage,data}
sudo mkdir -p /var/log/rendiff
sudo mkdir -p /etc/rendiff

# Set ownership
sudo chown -R rendiff:rendiff /opt/rendiff
sudo chown -R rendiff:rendiff /var/lib/rendiff
sudo chown -R rendiff:rendiff /var/log/rendiff
sudo chown -R rendiff:rendiff /etc/rendiff
```

#### Step 4: Clone and configure

```bash
# Switch to rendiff user
sudo su - rendiff

# Clone repository
cd /opt/rendiff
git clone https://github.com/rendiffdev/ffmpeg-api.git .

# Configure
cp .env.example /etc/rendiff/.env
cp config/storage.example.yml /etc/rendiff/storage.yml

# Edit configuration
nano /etc/rendiff/.env
```

#### Step 5: Set up systemd service

```bash
# Create service file
sudo tee /etc/systemd/system/rendiff.service > /dev/null <<EOF
[Unit]
Description=Rendiff FFmpeg API Service
Requires=docker.service
After=docker.service

[Service]
Type=simple
User=rendiff
WorkingDirectory=/opt/rendiff
EnvironmentFile=/etc/rendiff/.env
ExecStart=/usr/bin/docker-compose up
ExecStop=/usr/bin/docker-compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable rendiff
sudo systemctl start rendiff
```

## Manual Installation

For development or custom deployments:

### 1. Install Python environment

```bash
# Install Python 3.12
sudo apt install python3.12 python3.12-venv python3.12-dev

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Install FFmpeg

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# Or compile from source for latest version
wget https://ffmpeg.org/releases/ffmpeg-6.0.tar.xz
tar xf ffmpeg-6.0.tar.xz
cd ffmpeg-6.0
./configure --enable-gpl --enable-libx264 --enable-libx265
make -j$(nproc)
sudo make install
```

### 3. Database Setup (Automatic)

```bash
# SQLite database is automatically created
# No external database installation required!
# Database file will be created at: data/rendiff.db
mkdir -p data
```

### 4. Set up Valkey/Redis

```bash
# Install Redis (Valkey compatible)
sudo apt install redis-server

# Configure Redis
sudo nano /etc/redis/redis.conf
# Set: maxmemory 2gb
# Set: maxmemory-policy allkeys-lru

# Restart Redis
sudo systemctl restart redis
```

### 5. Run the application

```bash
# Initialize database (automatic on first run)
python scripts/init-sqlite.py

# Start API server
uvicorn api.main:app --host 0.0.0.0 --port 8000

# In another terminal, start worker
python -m worker.main
```

## Kubernetes Deployment

### 1. Using Helm (Recommended)

```bash
# Add Rendiff Helm repository
helm repo add rendiff https://charts.rendiff.dev
helm repo update

# Install with default values
helm install rendiff rendiff/rendiff

# Or with custom values
helm install rendiff rendiff/rendiff -f values.yaml
```

### 2. Using Raw Manifests

```bash
# Apply namespace
kubectl create namespace rendiff

# Apply configurations
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml

# Deploy services
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/valkey-deployment.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml

# Expose service
kubectl apply -f k8s/ingress.yaml
```

## Configuration

### Environment Variables

Key environment variables to configure:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Database (SQLite - no external setup required)
DATABASE_URL=sqlite:///data/rendiff.db

# Queue
VALKEY_URL=redis://localhost:6379

# Storage
STORAGE_CONFIG=/etc/rendiff/storage.yml
STORAGE_PATH=/var/lib/rendiff/storage

# Security
ENABLE_API_KEYS=true
API_KEY_HEADER=X-API-Key

# Resources
MAX_UPLOAD_SIZE=10737418240  # 10GB
MAX_JOB_DURATION=21600        # 6 hours
```

### Storage Configuration

Edit `storage.yml` to configure storage backends:

```yaml
storage:
  default_backend: local
  backends:
    local:
      type: filesystem
      base_path: /var/lib/rendiff/storage
    
    s3:
      type: s3
      endpoint: https://s3.amazonaws.com
      bucket: my-rendiff-bucket
      access_key: ${S3_ACCESS_KEY}
      secret_key: ${S3_SECRET_KEY}
```

### GPU Support

To enable GPU acceleration:

1. Install NVIDIA drivers and Docker GPU support:
```bash
# Install NVIDIA drivers
sudo apt install nvidia-driver-525

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
```

2. Enable GPU workers in `docker-compose.yml`:
```bash
docker-compose --profile gpu up -d
```

## Troubleshooting

### Common Issues

#### 1. Port already in use
```bash
# Find process using port 8080
sudo lsof -i :8080

# Change port in .env file
API_PORT=8081
```

#### 2. Database connection failed
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connection
psql -h localhost -U rendiff -d rendiff

# Check logs
docker-compose logs postgres
```

#### 3. FFmpeg not found
```bash
# Verify FFmpeg installation
docker exec rendiff_worker_1 ffmpeg -version

# For manual installation
which ffmpeg
ffmpeg -version
```

#### 4. Storage permission errors
```bash
# Fix permissions
sudo chown -R $(id -u):$(id -g) ./storage
chmod -R 755 ./storage
```

### Getting Help

- Check logs: `docker-compose logs -f`
- API documentation: http://localhost:8080/docs
- GitHub Issues: https://github.com/rendiffdev/ffmpeg-api/issues
- Website: https://rendiff.dev
- Email: dev@rendiff.dev
- Twitter/X: @rendiffdev

## Next Steps

1. [Configure storage backends](STORAGE.md)
2. [Set up monitoring](MONITORING.md)
3. [Review API documentation](API.md)
4. [Production best practices](PRODUCTION.md)
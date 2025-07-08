# Rendiff FFmpeg API - Setup Guide

Complete setup guide for the Rendiff FFmpeg API platform. This guide covers all deployment scenarios from development to production.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Setup Options](#setup-options)
3. [Development Setup](#development-setup)
4. [Production Setup](#production-setup)
5. [GenAI Setup](#genai-setup)
6. [HTTPS/SSL Configuration](#httpssl-configuration)
7. [Configuration Management](#configuration-management)
8. [Troubleshooting](#troubleshooting)

## Quick Start

**Single command setup for any deployment type:**

```bash
# Clone and navigate
git clone https://github.com/rendiffdev/ffmpeg-api.git
cd ffmpeg-api

# Choose your setup type
./setup.sh --help                    # Show all options
./setup.sh --development             # Quick dev setup
./setup.sh --production              # Production with wizard
./setup.sh --standard                # Standard production
./setup.sh --genai                   # AI-enabled production
./setup.sh --interactive             # Full configuration wizard
```

## Setup Options

### 🚀 Quick Development
**Best for: Local development, testing, learning**

```bash
./setup.sh --development
```

**What you get:**
- SQLite database (no PostgreSQL needed)
- Local Redis
- Debug mode enabled
- No authentication required
- API available at http://localhost:8080

### 🏭 Standard Production
**Best for: Production deployment without AI features**

```bash
./setup.sh --standard
```

**What you get:**
- PostgreSQL database
- Redis queue system
- Prometheus monitoring
- API key authentication
- Production-optimized settings
- 2 CPU workers

### 🤖 GenAI Production
**Best for: AI-enhanced video processing**

```bash
./setup.sh --genai
```

**What you get:**
- Everything from Standard Production
- GPU support for AI processing
- AI models (Real-ESRGAN, VideoMAE, etc.)
- GenAI workers
- Enhanced analysis capabilities
- AI endpoints at `/api/genai/v1/*`

### 🛡️ Production with HTTPS
**Best for: Internet-facing deployments**

```bash
./setup.sh --production
# Choose option 2 or 4 for HTTPS
```

**What you get:**
- Traefik reverse proxy
- Automatic SSL certificates (Let's Encrypt)
- Security headers
- Rate limiting
- Access at https://your-domain.com

### ⚙️ Interactive Setup
**Best for: Custom configurations, first-time setup**

```bash
./setup.sh --interactive
```

**What you get:**
- Step-by-step configuration wizard
- Custom storage backends (S3, Azure, GCP)
- Custom SSL certificates
- Advanced networking options
- Database migration choices

## Development Setup

Perfect for local development and testing:

### Prerequisites
- Docker Desktop
- 4GB+ RAM
- 10GB+ disk space

### Setup Process
```bash
# 1. Quick setup
./setup.sh --development

# 2. Verify deployment
curl http://localhost:8080/api/v1/health

# 3. Access documentation
open http://localhost:8080/docs
```

### Development Features
- **Hot reload** enabled for code changes
- **Debug logging** for troubleshooting
- **No authentication** for easy testing
- **SQLite database** (portable, no setup)
- **Simplified storage** (local filesystem)

### Development Commands
```bash
# View logs
docker-compose logs -f api

# Restart API only
docker-compose restart api

# Access database
docker-compose exec api python -c "from api.database import engine; print(engine.url)"

# Run tests
docker-compose exec api pytest

# Check status
./setup.sh --status
```

## Production Setup

Enterprise-ready deployment with full security and monitoring:

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- 8GB+ RAM
- 50GB+ disk space
- Domain name (for HTTPS)

### Standard Production
```bash
# 1. Full setup
./setup.sh --standard

# 2. Validate deployment
./setup.sh --validate

# 3. Check all services
docker-compose -f docker-compose.prod.yml ps
```

### Production Features
- **PostgreSQL** database with optimizations
- **Redis** for queuing and caching
- **API key authentication** with rotation
- **Resource limits** and health checks
- **Prometheus metrics** collection
- **Grafana dashboards** for monitoring
- **Production logging** configuration

### Production with HTTPS
```bash
# 1. Configure domain
export DOMAIN_NAME=your-domain.com
export CERTBOT_EMAIL=admin@your-domain.com

# 2. Setup with HTTPS
./setup.sh --production
# Choose option 2 for HTTPS

# 3. Verify SSL
curl -I https://your-domain.com/api/v1/health
```

### Production Commands
```bash
# Generate API keys
./scripts/manage-api-keys.sh generate

# Manage SSL certificates
./scripts/manage-ssl.sh list
./scripts/manage-ssl.sh renew

# Monitor services
./scripts/health-check.sh

# Backup data
./scripts/backup.sh create

# View production logs
docker-compose -f docker-compose.prod.yml logs -f

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale worker-cpu=4
```

## GenAI Setup

AI-enhanced video processing with GPU acceleration:

### Prerequisites
- NVIDIA GPU with 8GB+ VRAM
- NVIDIA Docker runtime
- CUDA 11.8+ drivers
- 16GB+ system RAM
- 100GB+ disk space (for AI models)

### Setup Process
```bash
# 1. Verify GPU support
nvidia-smi

# 2. Setup GenAI environment
./setup.sh --genai

# 3. Wait for model downloads (may take 10-30 minutes)
docker-compose logs -f model-downloader

# 4. Verify GenAI endpoints
curl http://localhost:8080/api/genai/v1/health
```

### GenAI Features
- **Real-ESRGAN** upscaling (2x, 4x)
- **VideoMAE** scene analysis
- **VMAF** quality prediction
- **AI-powered** encoding optimization
- **Content analysis** (complexity, scenes)
- **Automated** bitrate ladders

### GenAI Commands
```bash
# Check GPU utilization
docker-compose exec worker-genai nvidia-smi

# Download additional models
docker-compose -f docker-compose.genai.yml --profile setup run model-downloader

# Scale GenAI workers
docker-compose -f docker-compose.genai.yml up -d --scale worker-genai=2

# View GenAI logs
docker-compose logs -f worker-genai
```

### AI Endpoints
```bash
# Scene detection
POST /api/genai/v1/analyze/scenes

# Video upscaling
POST /api/genai/v1/enhance/upscale

# Quality prediction
POST /api/genai/v1/predict/quality

# Encoding optimization
POST /api/genai/v1/optimize/parameters
```

## HTTPS/SSL Configuration

Secure deployment with automatic SSL certificates:

### Domain Setup
```bash
# 1. Point your domain to the server
# 2. Configure domain in environment
export DOMAIN_NAME=api.example.com
export CERTBOT_EMAIL=admin@example.com

# 3. Setup with automatic SSL
./setup.sh --production
# Choose HTTPS option
```

### Manual SSL Management
```bash
# Generate Let's Encrypt certificate
./scripts/manage-ssl.sh generate-letsencrypt api.example.com admin@example.com

# Generate self-signed certificate (testing)
./scripts/manage-ssl.sh generate-self-signed api.example.com

# Test SSL configuration
./scripts/manage-ssl.sh test api.example.com

# Renew certificates
./scripts/manage-ssl.sh renew

# List certificates
./scripts/manage-ssl.sh list
```

### SSL Features
- **Automatic renewal** of Let's Encrypt certificates
- **Security headers** (HSTS, CSP, etc.)
- **TLS 1.2/1.3** support
- **Perfect forward secrecy**
- **Certificate monitoring** and alerts

## Configuration Management

### Environment Variables
```bash
# View current configuration
cat .env

# Edit configuration
nano .env

# Reload configuration
docker-compose restart api
```

### Key Configuration Files
- **`.env`** - Main environment configuration
- **`config/storage.yml`** - Storage backend configuration
- **`traefik/traefik.yml`** - Reverse proxy configuration
- **`monitoring/prometheus.yml`** - Metrics configuration

### API Key Management
```bash
# Generate new keys
./scripts/manage-api-keys.sh generate

# List current keys (masked)
./scripts/manage-api-keys.sh list

# Test key validity
./scripts/manage-api-keys.sh test

# Rotate all keys
./scripts/manage-api-keys.sh rotate

# Export keys for external use
./scripts/manage-api-keys.sh export
```

### Storage Configuration
```yaml
# config/storage.yml
storage:
  default_backend: "s3"  # or "local"
  backends:
    s3:
      type: "s3"
      bucket: "my-video-bucket"
      region: "us-east-1"
      access_key: "${AWS_ACCESS_KEY_ID}"
      secret_key: "${AWS_SECRET_ACCESS_KEY}"
```

## Troubleshooting

### Common Issues

#### 🚨 Services Won't Start
```bash
# Check Docker status
docker ps -a

# View error logs
docker-compose logs api

# Validate configuration
./setup.sh --validate

# Check resource usage
docker stats
```

#### 🔑 Authentication Issues
```bash
# Verify API keys
./scripts/manage-api-keys.sh list

# Test API access
curl -H "X-API-Key: your-key" http://localhost:8080/api/v1/health

# Regenerate keys if needed
./scripts/manage-api-keys.sh generate
```

#### 🌐 Network Issues
```bash
# Check port conflicts
netstat -tulpn | grep :8080

# Verify Docker networks
docker network ls

# Test internal connectivity
docker-compose exec api curl redis:6379
```

#### 💾 Database Issues
```bash
# Check database status
docker-compose exec postgres pg_isready

# View database logs
docker-compose logs postgres

# Run migrations manually
docker-compose exec api alembic upgrade head

# Reset database (destructive)
docker-compose down -v
./setup.sh --standard
```

#### 🤖 GenAI Issues
```bash
# Check GPU availability
nvidia-smi

# Verify CUDA in container
docker-compose exec worker-genai nvidia-smi

# Check model downloads
ls -la models/genai/

# Restart GenAI services
docker-compose restart worker-genai
```

### Performance Optimization

#### Resource Scaling
```bash
# Scale API instances
docker-compose up -d --scale api=3

# Scale CPU workers
docker-compose up -d --scale worker-cpu=4

# Scale GenAI workers (if GPU memory allows)
docker-compose up -d --scale worker-genai=2
```

#### Database Optimization
```bash
# Monitor database performance
docker-compose exec postgres psql -U ffmpeg_user -d ffmpeg_api -c "
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 10;"

# Analyze table usage
docker-compose exec postgres psql -U ffmpeg_user -d ffmpeg_api -c "
SELECT schemaname,tablename,attname,n_distinct,correlation 
FROM pg_stats WHERE tablename='jobs';"
```

### Getting Help

1. **Check logs**: `docker-compose logs -f [service]`
2. **Validate setup**: `./setup.sh --validate`
3. **Health check**: `./scripts/health-check.sh`
4. **Documentation**: Browse `/docs` in this repository
5. **Issues**: Report at GitHub repository issues page

---

## 📚 Documentation Navigation

| Guide | Description | When to Use |
|-------|-------------|-------------|
| **[🏠 Main README](../README.md)** | Project overview and quick start | Start here |
| **[🚀 Setup Guide](SETUP.md)** | Complete deployment guide | **You are here** |
| **[🔧 API Reference](API.md)** | Detailed API documentation | Using the API |
| **[📦 Installation Guide](INSTALLATION.md)** | Advanced installation options | Custom installs |
| **[🏭 Deployment Guide](../DEPLOYMENT.md)** | Production best practices | Production setup |
| **[🛡️ Security Guide](../SECURITY.md)** | Security configuration | Security hardening |

**Need help?** Check the [troubleshooting section](#troubleshooting) or [open an issue](https://github.com/rendiffdev/ffmpeg-api/issues).
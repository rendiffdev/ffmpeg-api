# Rendiff FFmpeg API

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-6.0-green)](https://ffmpeg.org/)

> **🎉 Production-Ready, Enterprise-Grade FFmpeg Processing API**

A self-hosted, production-ready FFmpeg processing API with multi-storage backend support, automatic setup, and comprehensive monitoring.

## ✨ Key Features

- **🎬 RESTful API** for video/audio processing using FFmpeg
- **☁️ Multi-Cloud Storage** (Local, AWS S3, S3-compatible storage)
- **⚡ Async Processing** with Celery workers and Redis queue
- **📊 Quality Analysis** with VMAF, PSNR, SSIM metrics
- **🔄 Real-time Progress** via Server-Sent Events (SSE)
- **🐳 Docker Ready** with GPU support and auto-scaling
- **📈 Monitoring** with Prometheus metrics and health checks
- **🛠️ Setup Wizard** for easy configuration
- **📋 Unified CLI** for system management

## 🚀 Quick Start

### Option 1: Quick Start (Recommended)
```bash
git clone https://github.com/rendiffdev/ffmpeg-api.git
cd ffmpeg-api

# Start with default SQLite setup
docker-compose up -d

# Check health
curl http://localhost:8080/api/v1/health
```

### Option 2: Interactive Setup
```bash
git clone https://github.com/rendiffdev/ffmpeg-api.git
cd ffmpeg-api

# Run interactive setup wizard
docker-compose run --rm setup
```

### Option 3: Production Deployment
```bash
git clone https://github.com/rendiffdev/ffmpeg-api.git
cd ffmpeg-api

# Copy and configure
cp .env.example .env
cp config/storage.yml.example config/storage.yml
# Edit configuration files

# Deploy production stack
docker-compose -f docker-compose.prod.yml up -d
```

## 📖 Documentation

- **[🚀 Production Deployment Guide](DEPLOYMENT.md)** - Complete production setup
- **[⚙️ Installation Guide](docs/INSTALLATION.md)** - Setup and configuration
- **[📋 Production Readiness Assessment](PRODUCTION_READINESS_ASSESSMENT.md)** - What's included and ready
- **[📚 API Documentation](docs/API.md)** - Complete API reference

### Quick Links
- **API Docs**: http://localhost:8080/docs
- **Health Check**: http://localhost:8080/api/v1/health
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

## 🔧 Unified CLI

Rendiff includes a comprehensive CLI for all operations:

```bash
# Management commands
./rendiff info                    # System information
./rendiff health                  # Health check
./rendiff service start          # Start services
./rendiff service status         # Service status

# Setup commands  
./rendiff setup wizard           # Interactive setup
./rendiff setup gpu              # GPU detection

# Storage management
./rendiff storage list           # List storage backends
./rendiff storage test s3        # Test storage connection

# System maintenance
./rendiff system backup          # Create backup
./rendiff system update          # Check/install updates
./rendiff system verify          # Verify system integrity

# FFmpeg tools
./rendiff ffmpeg version         # FFmpeg version info
./rendiff ffmpeg capabilities    # Hardware acceleration status
./rendiff ffmpeg probe video.mp4 # Analyze media file
```

## 🏗️ Core API Endpoints

### Video Processing
```bash
# Convert video
POST /api/v1/convert
{
  "input_path": "s3://bucket/input.mp4",
  "output_path": "s3://bucket/output.mp4", 
  "options": {
    "format": "mp4",
    "video_codec": "h264",
    "audio_codec": "aac"
  }
}

# Analyze quality
POST /api/v1/analyze
{
  "reference_path": "s3://bucket/original.mp4",
  "test_path": "s3://bucket/encoded.mp4"
}
```

### Job Management
```bash
GET  /api/v1/jobs              # List jobs
GET  /api/v1/jobs/{id}         # Job details  
GET  /api/v1/jobs/{id}/events  # Real-time progress (SSE)
DELETE /api/v1/jobs/{id}       # Cancel job
```

### System Information
```bash
GET /api/v1/health             # Health check
GET /api/v1/capabilities       # System capabilities
GET /api/v1/workers           # Worker status
GET /api/v1/storage           # Storage backend status
```

## ☁️ Multi-Cloud Storage Support

### Supported Backends
- **Local Filesystem** - Direct file storage ✅
- **AWS S3** - Amazon S3 and S3-compatible (MinIO) ✅
- **Azure Blob Storage** - Microsoft Azure storage ⚠️ *Configuration only*
- **Google Cloud Storage** - Google Cloud storage ⚠️ *Configuration only*
- **NFS** - Network File System mounting ⚠️ *Configuration only*

### Easy Configuration
```yaml
# config/storage.yml
storage:
  default_backend: "s3"
  backends:
    s3:
      type: "s3"
      bucket: "my-video-bucket"
      region: "us-east-1"
      # Credentials from environment variables
    azure:
      type: "azure" 
      container: "videos"
      account_name: "mystorageaccount"
```

### Environment-Based Setup
```bash
# AWS S3
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_S3_BUCKET=your-bucket

# Azure
AZURE_STORAGE_ACCOUNT=your_account
AZURE_STORAGE_KEY=your_key
AZURE_CONTAINER=videos

# Auto-setup will configure storage automatically
RENDIFF_AUTO_SETUP=true docker-compose up -d
```

## 🔐 Security & Production Features

### Built-in Security
- **🔑 API Key Authentication** with header/bearer token support
- **🛡️ Input Validation** and sanitization
- **🔒 Non-root Containers** for security
- **📝 Rate Limiting** via KrakenD API Gateway
- **🚫 IP Whitelisting** support
- **🛡️ Security Headers** middleware

### Production Ready
- **📊 Health Checks** at all levels
- **📈 Prometheus Metrics** collection
- **🏗️ Resource Limits** and scaling configuration
- **🗃️ Database Migrations** with Alembic
- **🐳 Multi-stage Docker builds** with optimization
- **⚡ Hardware Acceleration** (NVENC, QSV, VAAPI)

## 📊 Monitoring & Observability

### Metrics Available
- API response times and error rates
- Job processing statistics  
- Storage backend performance
- Worker health and utilization
- FFmpeg processing metrics

### Monitoring Features
- **Grafana Setup** - Basic dashboard configuration included
- **Health Endpoints** - Detailed component status checking
- **Real-time Progress** - Job processing updates via SSE
- **Worker Monitoring** - Celery worker status and statistics

## 🎛️ Configuration Options

### Basic Environment Variables
```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8080
API_WORKERS=4
EXTERNAL_URL=https://rendiff.yourdomain.com

# Resource Limits
MAX_UPLOAD_SIZE=10737418240     # 10GB
MAX_CONCURRENT_JOBS_PER_KEY=10
CPU_WORKERS=4
GPU_WORKERS=2

# Security
ENABLE_API_KEYS=true
RENDIFF_API_KEY=your-secure-32-char-api-key

# Database (SQLite default, PostgreSQL for production)
DATABASE_URL=sqlite+aiosqlite:///data/rendiff.db
# DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/rendiff
```

## 🚀 Scaling & Performance

### Horizontal Scaling
```bash
# Scale workers dynamically
docker-compose up -d --scale worker-cpu=6
docker-compose up -d --scale worker-gpu=2

# Scale API instances (remove container names for scaling)
docker-compose up -d --scale api=3
```

### Vertical Scaling
```yaml
# docker-compose.prod.yml
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '4.0'
    reservations:
      memory: 2G
      cpus: '2.0'
```

### GPU Acceleration
```bash
# Enable GPU workers
docker-compose --profile gpu up -d

# Check GPU status
./rendiff setup gpu
./rendiff ffmpeg capabilities
```

## 🔧 Development

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
mkdir -p data

# Start API server
python -m api.main

# Start worker
python -m worker.main
```

### Testing
```bash
# Check system health
curl http://localhost:8080/api/v1/health

# Test basic functionality
curl -H "X-API-Key: your-api-key" http://localhost:8080/api/v1/capabilities
```

## 🆘 Troubleshooting

### Quick Diagnostics
```bash
# Check system health
curl http://localhost:8080/api/v1/health

# View service logs
docker-compose logs -f api
docker-compose logs -f worker-cpu

# Check service status
docker-compose ps
```

### Common Issues
1. **Services won't start**: Check `docker-compose ps` and logs
2. **Storage errors**: Verify storage configuration in `config/storage.yml`
3. **FFmpeg errors**: Check if FFmpeg is properly installed in containers
4. **Database issues**: SQLite database is created automatically in `data/` directory

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🤝 Support & Community

- **🌐 Website**: [rendiff.dev](https://rendiff.dev)
- **📚 Documentation**: Complete guides in this repository
- **🐛 Issues**: [GitHub Issues](https://github.com/rendiffdev/ffmpeg-api/issues)  
- **💬 Discussions**: [GitHub Discussions](https://github.com/rendiffdev/ffmpeg-api/discussions)
- **🐙 GitHub**: [@rendiffdev](https://github.com/rendiffdev)
- **📧 Email**: [dev@rendiff.dev](mailto:dev@rendiff.dev)
- **🐦 Twitter/X**: [@rendiffdev](https://x.com/rendiffdev)

---

**Built with ❤️ by [Rendiff](https://rendiff.dev) using FastAPI, FFmpeg, Celery, and Docker**
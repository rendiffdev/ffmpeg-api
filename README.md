# Rendiff FFmpeg API

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-6.0-green)](https://ffmpeg.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)](https://postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-red)](https://redis.io/)

> **🚀 Production-Ready FFmpeg API with AI Enhancement**

A comprehensive, containerized FFmpeg processing API with optional AI features. Deploy with a single command - everything from development to enterprise production with GPU acceleration.

## ✨ Core Features

- **🎬 Complete FFmpeg API** - Process video/audio with RESTful endpoints
- **⚡ Async Processing** - Background jobs with real-time progress tracking
- **🤖 AI Enhancement** - Optional GPU-accelerated AI features (upscaling, analysis)
- **☁️ Multi-Cloud Storage** - S3, Azure, GCP, and local filesystem support
- **📊 Quality Analysis** - VMAF, PSNR, SSIM metrics and AI-powered insights
- **🛡️ Production Security** - API keys, HTTPS, rate limiting, monitoring
- **📈 Observability** - Prometheus metrics, Grafana dashboards, health checks
- **🐳 Docker Native** - Complete containerization with auto-scaling

## 🚀 Quick Start

### Choose Your Setup Type

```bash
# Clone repository
git clone https://github.com/rendiffdev/ffmpeg-api.git
cd ffmpeg-api

# Single command setup - choose your deployment type:
./setup.sh --development    # Quick local development
./setup.sh --standard       # Production (PostgreSQL, Redis, monitoring)
./setup.sh --genai          # AI-enhanced (GPU support, AI models)
./setup.sh --production     # Interactive production wizard
```

**That's it!** Your API will be running at `http://localhost:8080`

### 🏃‍♂️ Development (60 seconds)
Perfect for testing and local development:

```bash
./setup.sh --development
```
**Features:** SQLite, local storage, no auth required, debug mode

### 🏭 Standard Production 
Enterprise-ready deployment:

```bash
./setup.sh --standard
```
**Features:** PostgreSQL, Redis, monitoring, API keys, 2 CPU workers

### 🤖 AI-Enhanced Production
GPU-accelerated AI features:

```bash
./setup.sh --genai
```
**Features:** Everything in Standard + GPU workers, AI models, upscaling, scene analysis

## 📋 Deployment Comparison

| Feature | Development | Standard | GenAI |
|---------|------------|----------|-------|
| **Setup Time** | 1 minute | 3 minutes | 10 minutes |
| **Database** | SQLite | PostgreSQL | PostgreSQL |
| **Queue** | Redis | Redis | Redis |
| **Authentication** | Disabled | API Keys | API Keys |
| **Monitoring** | Basic | Full (Prometheus/Grafana) | Full |
| **Workers** | 1 CPU | 2 CPU | 2 CPU + 1 GPU |
| **AI Features** | ❌ | ❌ | ✅ |
| **GPU Support** | ❌ | ❌ | ✅ |
| **Production Ready** | ❌ | ✅ | ✅ |

## 🎯 API Endpoints

### Core Processing
```http
POST /api/v1/convert      # Universal media conversion
POST /api/v1/analyze      # Quality analysis (VMAF, PSNR, SSIM)
POST /api/v1/stream       # Generate HLS/DASH streaming
POST /api/v1/estimate     # Processing time estimates
```

### Job Management
```http
GET  /api/v1/jobs         # List and filter jobs
GET  /api/v1/jobs/{id}    # Job status and progress
GET  /api/v1/jobs/{id}/events  # Real-time progress (SSE)
DELETE /api/v1/jobs/{id}  # Cancel job
```

### AI Features (GenAI Setup)
```http
POST /api/genai/v1/enhance/upscale     # Real-ESRGAN 2x/4x upscaling
POST /api/genai/v1/analyze/scenes      # AI scene detection
POST /api/genai/v1/optimize/parameters # Smart encoding optimization
POST /api/genai/v1/predict/quality     # Quality prediction
```

### System & Health
```http
GET  /api/v1/health       # Service health check
GET  /api/v1/capabilities # Supported formats and features
GET  /docs                # Interactive API documentation
```

## 🔧 Configuration & Management

### API Key Management
```bash
# Generate secure API keys
./scripts/manage-api-keys.sh generate

# List current keys (masked)
./scripts/manage-api-keys.sh list

# Test API access
curl -H "X-API-Key: your-key" http://localhost:8080/api/v1/health
```

### HTTPS/SSL Setup
```bash
# Configure your domain
export DOMAIN_NAME=api.yourdomain.com
export CERTBOT_EMAIL=admin@yourdomain.com

# Setup with automatic SSL
./setup.sh --production
# Choose HTTPS option for Let's Encrypt certificates
```

### Monitoring & Health
```bash
# Check deployment status
./setup.sh --status

# Validate configuration
./setup.sh --validate

# Health check all services
./scripts/health-check.sh

# View logs
docker-compose logs -f api
```

## 📊 What's Included

### 🔧 **Core Infrastructure**
- **FastAPI** - Modern async web framework
- **Celery** - Distributed task processing
- **PostgreSQL 15** - Production database with optimizations
- **Redis 7** - Queue and caching layer
- **FFmpeg 6.0** - Latest video processing capabilities

### 🛡️ **Security & Production**
- **API Key Authentication** with rotation support
- **Rate Limiting** at gateway and application level
- **HTTPS/SSL** with automatic Let's Encrypt certificates
- **Security Headers** (HSTS, CSP, XSS protection)
- **Network Isolation** via Docker networks
- **Resource Limits** and health monitoring

### 📈 **Monitoring & Observability**
- **Prometheus** metrics collection
- **Grafana** dashboards and visualizations
- **Structured Logging** with correlation IDs
- **Health Checks** for all services
- **Real-time Progress** via Server-Sent Events

### 🤖 **AI Features (Optional)**
- **Real-ESRGAN** - Video/image upscaling (2x, 4x)
- **VideoMAE** - Scene detection and analysis
- **VMAF Integration** - Perceptual quality metrics
- **Smart Encoding** - AI-optimized compression settings
- **Content Analysis** - Complexity and scene classification

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Traefik       │────│   KrakenD    │────│   FastAPI       │
│   (SSL/Proxy)   │    │   (Gateway)  │    │   (Core API)    │
└─────────────────┘    └──────────────┘    └─────────────────┘
                                                     │
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │    Redis     │    │   Celery        │
│   (Database)    │    │   (Queue)    │    │   (Workers)     │
└─────────────────┘    └──────────────┘    └─────────────────┘
                                                     │
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Prometheus    │    │   Grafana    │    │   GPU Workers   │
│   (Metrics)     │    │ (Dashboards) │    │   (AI/GenAI)    │
└─────────────────┘    └──────────────┘    └─────────────────┘
```

## 📖 Documentation

| Document | Description |
|----------|-------------|
| **[Setup Guide](docs/SETUP.md)** | Complete setup documentation for all deployment types |
| **[API Reference](docs/API.md)** | Detailed API endpoint documentation |
| **[Installation Guide](docs/INSTALLATION.md)** | Advanced installation and configuration |
| **[Deployment Guide](DEPLOYMENT.md)** | Production deployment best practices |
| **[Security Guide](SECURITY.md)** | Security configuration and best practices |

## 🎯 Use Cases

### 🎬 **Media Companies**
- Automated video transcoding pipelines
- Quality analysis and optimization
- Multi-format delivery (HLS, DASH, MP4)
- AI-enhanced upscaling for archive content

### 📺 **Streaming Platforms** 
- Adaptive bitrate ladder generation
- Real-time encoding for live streams
- Content analysis for recommendation engines
- Automated thumbnail generation

### 🏢 **Enterprise**
- Internal video processing workflows
- Compliance and quality monitoring
- Cost optimization through intelligent encoding
- Integration with existing media management systems

### 🔬 **Research & Development**
- Video analysis and metrics collection
- A/B testing for encoding parameters
- Machine learning dataset preparation
- Performance benchmarking

## 🛠️ Advanced Features

### Storage Backends
```yaml
# Configure multiple storage options
storage:
  backends:
    s3:          # AWS S3 or compatible
    azure:       # Azure Blob Storage  
    gcp:         # Google Cloud Storage
    local:       # Local filesystem
```

### GPU Acceleration
```bash
# Enable hardware acceleration
./setup.sh --genai

# Supports:
# - NVIDIA NVENC/NVDEC
# - Intel Quick Sync Video
# - AMD VCE/VCN
# - Apple VideoToolbox (macOS)
```

### Horizontal Scaling
```bash
# Scale API instances
docker-compose up -d --scale api=3

# Scale workers based on load
docker-compose up -d --scale worker-cpu=4
docker-compose up -d --scale worker-genai=2
```

## 🚀 Production Deployment

### Minimum Requirements
- **CPU:** 4 cores
- **RAM:** 8GB
- **Storage:** 50GB SSD
- **Network:** 1Gbps

### Recommended (GenAI)
- **CPU:** 8+ cores
- **RAM:** 32GB
- **GPU:** NVIDIA RTX 3080/4080 (8GB+ VRAM)
- **Storage:** 200GB NVMe SSD
- **Network:** 10Gbps

### Cloud Deployment
Supports deployment on:
- **AWS** (EC2, ECS, EKS)
- **Google Cloud** (GCE, GKE) 
- **Azure** (VM, AKS)
- **DigitalOcean** (Droplets, Kubernetes)
- **Self-hosted** infrastructure

## 📞 Support & Community

- **📚 Documentation**: Complete guides in `/docs`
- **🐛 Issues**: [GitHub Issues](https://github.com/rendiffdev/ffmpeg-api/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/rendiffdev/ffmpeg-api/discussions)
- **🔒 Security**: See [SECURITY.md](SECURITY.md)
- **📄 License**: [MIT License](LICENSE)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Built with ❤️ by the Rendiff team**

*Transform your video processing workflow with production-ready FFmpeg API and optional AI enhancement.*
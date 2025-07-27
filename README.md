# Production-Ready FFmpeg API

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?logo=fastapi)](https://fastapi.tiangolo.com/)
[![FFmpeg 6.0+](https://img.shields.io/badge/FFmpeg-6.0%2B-green)](https://ffmpeg.org/)

> **🚀 Enterprise-Grade FFmpeg Processing API**

A high-performance, production-ready FFmpeg API designed to replace complex CLI workflows with a modern, scalable, developer-friendly solution. Built for professional video processing with enterprise features.

## ✨ Key Features

- **🎬 Complete FFmpeg Capability** - Full CLI parity with REST API convenience
- **⚡ Hardware Acceleration** - NVENC, QSV, VAAPI, VideoToolbox support
- **📊 Quality Metrics** - Built-in VMAF, PSNR, SSIM analysis
- **🔄 Async Processing** - Non-blocking operations with real-time progress
- **🛡️ Enterprise Security** - API keys, rate limiting, input validation
- **📈 Production Monitoring** - Prometheus metrics, health checks, alerting
- **🌐 Multi-Cloud Storage** - S3, Azure, GCP, and local filesystem
- **🐳 Container Native** - Optimized Docker deployment with orchestration

## 🚀 Quick Start

### 1. Clone & Deploy (60 seconds)

```bash
git clone https://github.com/rendiffdev/ffmpeg-api.git
cd ffmpeg-api

# Choose your deployment type
./setup.sh --development    # Local development (SQLite)
./setup.sh --standard       # Production (PostgreSQL + Redis)
./setup.sh --gpu           # Hardware accelerated processing
```

### 2. Access Your API

```bash
# API available at
curl http://localhost:8000/api/v1/health

# Interactive documentation
open http://localhost:8000/docs
```

### 3. First Video Conversion

```bash
curl -X POST "http://localhost:8000/api/v1/convert" \\
  -H "Content-Type: application/json" \\
  -d '{
    "input": "/path/to/input.mp4",
    "output": "/path/to/output.webm",
    "operations": [
      {"type": "transcode", "params": {"video_codec": "vp9", "crf": 30}}
    ]
  }'
```

## 📋 Deployment Options

| Type | Use Case | Setup Time | Features |
|------|----------|------------|-----------|
| **Development** | Local testing | 60 seconds | SQLite, Debug mode, No auth |
| **Standard** | Production CPU | 3 minutes | PostgreSQL, Redis, HTTPS, Monitoring |
| **GPU** | Hardware accelerated | 5 minutes | Everything + NVENC/QSV/VAAPI |

## 🎯 API Capabilities

### Core Processing Endpoints

```http
POST /api/v1/convert        # Universal media conversion
POST /api/v1/analyze        # Quality metrics (VMAF, PSNR, SSIM)
POST /api/v1/stream         # HLS/DASH adaptive streaming
POST /api/v1/estimate       # Processing time/cost estimation
```

### Job Management

```http
GET  /api/v1/jobs           # List and filter jobs
GET  /api/v1/jobs/{id}      # Job status and progress
GET  /api/v1/jobs/{id}/events # Real-time progress (SSE)
DELETE /api/v1/jobs/{id}    # Cancel job
```

### System & Health

```http
GET  /api/v1/health         # Health check
GET  /api/v1/capabilities   # Supported formats and features
GET  /docs                  # Interactive API documentation
```

## 🏗️ Professional Features

### Hardware Acceleration

- **NVIDIA NVENC/NVDEC** - GPU encoding and decoding
- **Intel Quick Sync Video** - Hardware-accelerated processing
- **AMD VCE/VCN** - Advanced media framework
- **Apple VideoToolbox** - macOS hardware acceleration

### Quality Analysis

- **VMAF** - Perceptual video quality measurement
- **PSNR** - Peak Signal-to-Noise Ratio
- **SSIM** - Structural Similarity Index
- **Bitrate Analysis** - Compression efficiency metrics

### Enterprise Security

- **API Key Authentication** with role-based permissions
- **Rate Limiting** with configurable thresholds
- **Input Validation** prevents command injection
- **HTTPS/SSL** with automatic certificate management
- **Security Headers** (HSTS, CSP, XSS protection)

### Production Monitoring

- **Prometheus Metrics** - 50+ metrics tracked
- **Grafana Dashboards** - Real-time visualization
- **Health Checks** - Comprehensive system monitoring
- **Structured Logging** - Centralized log management
- **Alerting Rules** - Proactive issue detection

## 🐳 Docker Architecture

```yaml
Production Stack:
├── Traefik (SSL/Load Balancer)
├── KrakenD (API Gateway)
├── FastAPI (Core API)
├── Celery Workers (CPU/GPU)
├── PostgreSQL (Database)
├── Redis (Queue/Cache)
├── Prometheus (Metrics)
└── Grafana (Monitoring)
```

### Container Features

- **Multi-stage builds** for optimized images
- **Security hardening** with non-root users
- **Health checks** with automatic restarts
- **Resource limits** and monitoring
- **Log rotation** and management

## 📊 Format Support

### Input Formats

**Video:** MP4, AVI, MOV, MKV, WebM, FLV, WMV, MPEG, TS, VOB, 3GP, MXF
**Audio:** MP3, WAV, FLAC, AAC, OGG, WMA, M4A, Opus, ALAC, DTS

### Output Formats

**Containers:** MP4, WebM, MKV, MOV, HLS, DASH, AVI
**Video Codecs:** H.264, H.265/HEVC, VP9, AV1, ProRes
**Audio Codecs:** AAC, MP3, Opus, Vorbis, FLAC

## 🔧 Configuration

### Environment Variables

```bash
# Core Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/ffmpeg_api
REDIS_URL=redis://localhost:6379/0

# Security
ENABLE_API_KEYS=true
RATE_LIMIT_CALLS=2000
RATE_LIMIT_PERIOD=3600

# FFmpeg
FFMPEG_HARDWARE_ACCELERATION=auto
FFMPEG_THREADS=0
```

### Advanced Configuration

```yaml
# config/storage.yml - Multi-cloud storage
storage:
  backends:
    s3:
      bucket: my-video-bucket
      region: us-west-2
    azure:
      container: videos
    local:
      path: /storage
```

## 📈 Performance & Scaling

### Horizontal Scaling

```bash
# Scale API instances
docker compose up -d --scale api=4

# Scale workers based on load
docker compose up -d --scale worker-cpu=8
docker compose up -d --scale worker-gpu=2
```

### Performance Optimizations

- **Connection pooling** for database and Redis
- **Async processing** with non-blocking I/O
- **Hardware acceleration** auto-detection
- **Caching layers** for frequently accessed data
- **Resource management** with limits and monitoring

## 🛠️ Development

### Local Development Setup

```bash
# Development environment
./setup.sh --development

# Install development dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Code formatting
black api/ worker/ tests/
flake8 api/ worker/ tests/
```

### Testing

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Performance tests
pytest tests/performance/ -v
```

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[API Reference](docs/API.md)** | Complete API endpoint documentation |
| **[Setup Guide](docs/SETUP.md)** | Detailed installation instructions |
| **[Production Guide](docs/PRODUCTION.md)** | Production deployment best practices |
| **[Monitoring Guide](docs/MONITORING.md)** | Observability and alerting setup |

## 🚦 System Requirements

### Minimum (Standard)

- **CPU:** 4 cores
- **RAM:** 8GB
- **Storage:** 50GB SSD
- **Network:** 1Gbps

### Recommended (GPU)

- **CPU:** 8+ cores
- **RAM:** 32GB
- **GPU:** NVIDIA RTX 3080+ (8GB+ VRAM)
- **Storage:** 200GB NVMe SSD
- **Network:** 10Gbps

## 🌐 Cloud Deployment

Supports deployment on all major cloud platforms:

- **AWS** (EC2, ECS, EKS)
- **Google Cloud** (GCE, GKE)
- **Azure** (VM, AKS)
- **DigitalOcean** (Droplets, Kubernetes)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🚀 Why Choose This API?

### vs. FFmpeg CLI

| Feature | FFmpeg CLI | This API | Advantage |
|---------|------------|----------|-----------|
| **Batch Processing** | Manual scripting | Built-in API | **10x Easier** |
| **Progress Tracking** | Parse stderr | Real-time SSE | **Real-time** |
| **Error Handling** | Exit codes | Structured JSON | **Detailed** |
| **Quality Analysis** | Separate tools | Integrated | **Built-in** |
| **Scaling** | Manual | Auto-scaling | **Enterprise** |
| **Monitoring** | None | Full metrics | **Production** |

### vs. Other Solutions

- **Complete CLI Parity** - No feature compromises
- **Production Ready** - Battle-tested in enterprise environments
- **Developer Friendly** - Modern REST API with great docs
- **Cost Effective** - Self-hosted, no per-minute charges
- **Highly Secure** - Enterprise-grade security features

---

**Transform your video processing workflow with production-ready FFmpeg API.**

*Built with ❤️ by the Rendiff team*
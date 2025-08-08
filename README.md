# FFmpeg API

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?logo=fastapi)](https://fastapi.tiangolo.com/)
[![FFmpeg 6.0+](https://img.shields.io/badge/FFmpeg-6.0%2B-green)](https://ffmpeg.org/)

High-performance, production-ready FFmpeg API for professional video processing. Replace complex CLI workflows with a modern REST API featuring hardware acceleration, real-time progress tracking, and enterprise-grade security.

## ✨ Key Features

- **Complete FFmpeg Capability** - Full CLI parity with REST API convenience
- **Hardware Acceleration** - NVENC, QSV, VAAPI, VideoToolbox support
- **Quality Metrics** - Built-in VMAF, PSNR, SSIM analysis
- **Async Processing** - Non-blocking operations with real-time progress
- **Enterprise Security** - API keys, rate limiting, input validation
- **Production Monitoring** - Prometheus metrics, health checks, alerting
- **Multi-Cloud Storage** - S3, Azure, GCP, and local filesystem
- **Container Native** - Optimized Docker deployment with orchestration

## 🚀 Quick Start

```bash
# Clone and deploy
git clone https://github.com/yourusername/ffmpeg-api.git
cd ffmpeg-api
docker compose up -d

# API is now available at http://localhost:8000
curl http://localhost:8000/api/v1/health
```

For detailed setup options, see the [Setup Guide](docs/SETUP.md).

## 📋 API Endpoints

### Core Processing
```http
POST   /api/v1/convert     # Media conversion
POST   /api/v1/analyze     # Quality metrics (VMAF, PSNR, SSIM)
POST   /api/v1/stream      # HLS/DASH adaptive streaming
POST   /api/v1/batch       # Batch processing
```

### Job Management
```http
GET    /api/v1/jobs        # List jobs
GET    /api/v1/jobs/{id}   # Job status
DELETE /api/v1/jobs/{id}   # Cancel job
```

### System
```http
GET    /api/v1/health      # Health check
GET    /docs               # API documentation
```

## 🏗️ Architecture

```yaml
Services:
├── API (FastAPI)
├── Workers (Celery)
├── Queue (Redis)
├── Database (PostgreSQL/SQLite)
├── Storage (S3/Local)
└── Monitoring (Prometheus/Grafana)
```

## 📊 Format Support

**Input:** MP4, AVI, MOV, MKV, WebM, FLV, MP3, WAV, FLAC, AAC, and more  
**Output:** MP4, WebM, MKV, HLS, DASH with H.264, H.265, VP9, AV1 codecs

## 🔧 Configuration

Configuration via environment variables or `.env` file:

```bash
# Core
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=postgresql://user:pass@localhost/ffmpeg_api
REDIS_URL=redis://localhost:6379

# Security
ENABLE_API_KEYS=true
RATE_LIMIT_CALLS=2000
RATE_LIMIT_PERIOD=3600

# Hardware
FFMPEG_HARDWARE_ACCELERATION=auto
```

## 📚 Documentation

- [Setup Guide](docs/SETUP.md) - Detailed installation instructions
- [API Reference](docs/API.md) - Complete endpoint documentation
- [Deployment Guide](DEPLOYMENT.md) - Production deployment
- [Runbooks](docs/RUNBOOKS.md) - Operational procedures
- [Contributing](CONTRIBUTING.md) - Development guidelines
- [Security](SECURITY.md) - Security policies

## 🚦 System Requirements

### Minimum
- CPU: 4 cores
- RAM: 8GB
- Storage: 50GB

### Recommended (Production)
- CPU: 8+ cores
- RAM: 32GB
- GPU: NVIDIA/AMD for hardware acceleration
- Storage: 200GB+ SSD

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Built with FastAPI, FFmpeg 6.0+, and Docker for professional video processing workflows.*
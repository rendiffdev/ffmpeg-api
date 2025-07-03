# Rendiff FFmpeg API

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-6.0-green)](https://ffmpeg.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)](https://postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-red)](https://redis.io/)

> **🚀 Zero-Configuration, Production-Ready FFmpeg API with Full Docker Automation**

A **completely containerized** FFmpeg processing API that starts with **one command**. No database setup, no Redis configuration, no manual steps - everything is automated and production-ready out of the box.

## ✨ Core Features

- **🎬 RESTful API** for video/audio processing using FFmpeg
- **☁️ Multi-Backend Storage** (Local filesystem, AWS S3 compatible)
- **⚡ Async Processing** with Celery workers and Redis queue
- **📊 Quality Analysis** with VMAF, PSNR, SSIM metrics
- **🔄 Real-time Progress** via Server-Sent Events (SSE)
- **🐳 Docker Ready** with GPU support and auto-scaling
- **📈 Monitoring** with Prometheus metrics and health checks
- **🛠️ Setup Wizard** for easy configuration
- **📋 Unified CLI** for system management
- **🤖 Optional AI Enhancement** with GenAI features

## 🚀 Quick Start

### Standard Deployment (Default) - Fully Configured
```bash
git clone https://github.com/rendiffdev/ffmpeg-api.git
cd ffmpeg-api

# Copy environment template (optional - works with defaults)
cp .env.example .env

# Deploy with automated database setup
./deploy.sh standard

# OR start directly (includes automatic DB migration)
docker-compose up -d
```

### AI-Enhanced Deployment (Optional) - GPU Required
```bash
# Enable GenAI features (requires NVIDIA GPU + Docker runtime)
export GENAI_ENABLED=true
export GENAI_GPU_ENABLED=true

# Deploy with automated setup (includes DB + AI models)
./deploy.sh genai

# OR manual deployment
docker-compose -f docker-compose.yml -f docker-compose.genai.yml up -d
```

### 🎯 What's Included Out-of-the-Box
- ✅ **PostgreSQL 15** - Fully configured with optimized settings
- ✅ **Redis 7** - Pre-configured for video processing workloads  
- ✅ **Database Schema** - Automatically created with migrations
- ✅ **Health Checks** - All services monitored and self-healing
- ✅ **Production Settings** - Optimized for video processing performance
- ✅ **No Manual Setup** - Everything works immediately after `docker-compose up`

Your API will be available at:
- **API**: http://localhost:8080 (via KrakenD gateway)
- **Docs**: http://localhost:8080/docs  
- **Monitoring**: http://localhost:3000 (Grafana)

## 🎯 API Endpoints

### Core Video Processing
```
POST /api/v1/convert    - Process video/audio files
GET  /api/v1/jobs       - List and track jobs
GET  /api/v1/jobs/{id}  - Get job status and progress
GET  /api/v1/health     - API health status
```

### AI-Enhanced Features (Optional - when `GENAI_ENABLED=true`)
```
# Content Analysis
POST /api/genai/v1/analyze/scenes         - AI scene detection
POST /api/genai/v1/analyze/complexity     - Video complexity analysis  
POST /api/genai/v1/analyze/content-type   - Content classification

# Quality Enhancement
POST /api/genai/v1/enhance/upscale        - Real-ESRGAN upscaling
POST /api/genai/v1/enhance/denoise        - AI denoising
POST /api/genai/v1/enhance/restore        - Video restoration

# Encoding Optimization
POST /api/genai/v1/optimize/parameters    - FFmpeg optimization
POST /api/genai/v1/optimize/bitrate-ladder - Adaptive streaming ladder
POST /api/genai/v1/optimize/compression   - Compression optimization

# Quality Prediction
POST /api/genai/v1/predict/quality        - VMAF/DOVER assessment
POST /api/genai/v1/predict/encoding-quality - Pre-encoding prediction
POST /api/genai/v1/predict/bandwidth-quality - Quality curves

# Complete Pipelines
POST /api/genai/v1/pipeline/smart-encode  - Complete AI pipeline
POST /api/genai/v1/pipeline/adaptive-streaming - Multi-bitrate package
```

## 📝 Basic Usage Examples

### Standard Video Processing
```bash
# Convert video
curl -X POST "http://localhost:8080/api/v1/convert" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/input/video.mp4",
    "output_path": "/output/converted.mp4",
    "operations": [
      {"type": "transcode", "codec": "h264", "crf": 23}
    ]
  }'
```

### AI-Enhanced Processing (when GenAI enabled)
```bash
# Smart encoding with AI optimization
curl -X POST "http://localhost:8080/api/genai/v1/pipeline/smart-encode" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "video_path": "/input/video.mp4",
    "quality_preset": "high",
    "optimization_level": 2
  }'

# AI upscaling
curl -X POST "http://localhost:8080/api/genai/v1/enhance/upscale" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "video_path": "/input/video.mp4",
    "scale_factor": 4,
    "model_variant": "RealESRGAN_x4plus"
  }'
```

## 🏗️ Architecture

### Standard Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   KrakenD       │    │   FastAPI       │    │   Celery        │
│   (Gateway)     │───▶│   (REST API)    │───▶│   (Workers)     │
│   Port 8080     │    │   Port 8000     │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       ▼                       ▼
         │              ┌─────────────────┐    ┌─────────────────┐
         │              │   PostgreSQL    │    │   FFmpeg        │
         │              │   (Metadata)    │    │   (Processing)  │
         │              └─────────────────┘    └─────────────────┘
         ▼                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Monitoring    │    │   Redis         │    │   Storage       │
│   (Grafana)     │    │   (Queue)       │    │   (Files)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### AI-Enhanced Architecture (Optional)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   GenAI         │    │   FFmpeg        │
│   (REST API)    │───▶│   (AI Services) │───▶│   (Processing)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐               │
         │              │   AI Models     │               │
         │              │   (GPU)         │               │
         │              └─────────────────┘               │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   Redis         │    │   Storage       │
│   (Metadata)    │    │   (Queue)       │    │   (Files)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🤖 AI Features (Optional)

### Core Principle
**FFmpeg remains the mandatory core encoder** - GenAI only provides intelligent decision-making and pre/post-processing:

- ✅ FFmpeg = Permanent, unchangeable encoding engine
- ✅ GenAI = Smart assistant that optimizes FFmpeg parameters
- ✅ GenAI enhances video before/after FFmpeg processing
- ❌ GenAI never replaces FFmpeg

### 1. Content Analysis
- **Scene Detection**: PySceneDetect + VideoMAE for intelligent scene boundaries
- **Complexity Analysis**: AI-powered assessment of video complexity
- **Content Classification**: Automatic categorization (action, dialogue, landscape, etc.)

### 2. Quality Enhancement
- **AI Upscaling**: Real-ESRGAN for 2x, 4x, 8x upscaling
- **Noise Reduction**: AI-powered denoising
- **Video Restoration**: Repair old or damaged videos

### 3. Encoding Optimization
- **Parameter Optimization**: AI-suggested FFmpeg parameters
- **Bitrate Ladder Generation**: Per-title adaptive streaming optimization
- **Compression Optimization**: Quality vs. size balance using AI

### 4. Quality Prediction
- **VMAF + DOVER**: Comprehensive quality assessment
- **Pre-encoding Prediction**: Quality estimation before processing
- **Bandwidth-Quality Curves**: Adaptive streaming optimization

### 5. Complete Pipelines
- **Smart Encoding**: Complete AI-enhanced encoding workflow
- **Adaptive Streaming**: AI-optimized multi-bitrate packaging

### AI Hardware Requirements
- **GPU**: NVIDIA RTX 3090 (24GB VRAM) or better
- **Recommended**: NVIDIA A100 (40GB VRAM)
- **CPU Fallback**: Available but significantly slower

## 🔧 Configuration

### ⚡ Zero-Configuration Setup
The API works out-of-the-box with secure defaults. **No database setup required!**

```bash
# Simply run and everything is configured automatically:
docker-compose up -d

# PostgreSQL, Redis, and all services start with production-ready settings
# Database schema is created automatically via migrations
# Health checks ensure everything is ready before API starts
```

### 🛠️ Optional Customization
```bash
# Copy template if you want to customize (optional)
cp .env.example .env

# Common customizations:
STORAGE_BACKEND=s3                    # Use S3 instead of local storage
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_S3_BUCKET=your-bucket

API_KEY_HEADER=X-API-Key              # Custom auth header
ENABLE_API_KEYS=true                  # Enable API key auth

# GenAI Features (requires GPU)
GENAI_ENABLED=true                    # Enable AI features
GENAI_GPU_ENABLED=true                # Use GPU acceleration
GENAI_GPU_DEVICE=cuda:0               # GPU device
```

### 🗄️ Database & Queue (Fully Managed)
```bash
# ✅ PostgreSQL 15 - Production optimized, auto-configured
# ✅ Redis 7 - Video processing optimized, persistent queues
# ✅ Schema migrations - Automatic on startup
# ✅ Health monitoring - Built-in checks for all services
# ✅ Data persistence - Volumes managed automatically
# ✅ Connection pooling - Optimized for high concurrency
```

### 💾 Storage Backends (Auto-Configured)
- **✅ Local**: File system storage (default, ready to use)
- **✅ S3**: Amazon S3 or S3-compatible storage (MinIO, DigitalOcean Spaces, etc.)
- **📋 Planned**: Azure Blob, Google Cloud Storage, NFS (future releases)

## 📊 Monitoring & Observability

### Included Monitoring Stack
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards  
- **Health Checks**: Endpoint monitoring
- **Logging**: Structured JSON logs

### Key Metrics
- Processing times and throughput
- Queue lengths and worker status
- Resource utilization (CPU, memory, GPU)
- Error rates and success ratios
- Storage usage and transfer rates

### Grafana Dashboards
Access at http://localhost:3000 (admin/admin):
- **API Performance**: Request metrics and response times
- **Worker Status**: Celery worker health and queue status
- **System Resources**: CPU, memory, and disk usage
- **GenAI Metrics**: AI model performance and GPU utilization (if enabled)

## 🐳 Docker Deployment

### Standard Deployment
```bash
# Start all services
docker-compose up -d

# Scale workers
docker-compose up -d --scale worker=4

# View logs
docker-compose logs -f api worker
```

### AI-Enhanced Deployment
```bash
# Requires NVIDIA Docker runtime
docker-compose -f docker-compose.genai.yml up -d

# Download AI models (one-time)
docker-compose -f docker-compose.genai.yml --profile setup up model-downloader

# Scale AI workers
docker-compose -f docker-compose.genai.yml up -d --scale worker-genai=2
```

### Production Docker Setup
```bash
# Production with external database
export DATABASE_URL=postgresql://user:pass@prod-db:5432/ffmpeg
export REDIS_URL=redis://prod-redis:6379/0

docker-compose -f docker-compose.prod.yml up -d
```

## 🔐 Security

### API Authentication
- API key-based authentication
- IP whitelisting support
- Rate limiting (per-key and global)
- Secure header validation

### Security Headers
- HSTS (HTTP Strict Transport Security)
- Content Security Policy (CSP)
- X-Frame-Options protection
- CORS configuration

### Best Practices
- Run containers as non-root users
- Network isolation between services
- Secrets management via environment variables
- Regular security updates

## 📈 Performance & Scaling

### Horizontal Scaling
```bash
# Scale API instances
docker-compose up -d --scale api=3

# Scale workers
docker-compose up -d --scale worker=8

# Scale with AI workers
docker-compose -f docker-compose.genai.yml up -d --scale worker-genai=4
```

### Performance Optimization
- **Hardware acceleration**: GPU encoding support
- **Concurrent processing**: Multi-worker setup
- **Queue optimization**: Redis-based job queue
- **Caching**: Result caching for repeated operations
- **Storage optimization**: Multi-backend support with CDN integration

### Resource Requirements
- **Minimum**: 2 CPU cores, 4GB RAM
- **Recommended**: 4+ CPU cores, 8GB+ RAM
- **With GenAI**: 8+ CPU cores, 16GB+ RAM, 24GB+ GPU VRAM

## 🛠️ Development

### Local Development Setup
```bash
# Clone repository
git clone https://github.com/rendiffdev/ffmpeg-api.git
cd ffmpeg-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Optional: Install GenAI dependencies
pip install -r requirements-genai.txt

# Set up environment
cp .env.example .env
# Edit .env with your settings

# Run locally
python -m api.main
```

### Testing
```bash
# Run tests
python -m pytest tests/

# Test API endpoints
curl http://localhost:8080/api/v1/health

# Test GenAI endpoints (if enabled)
curl http://localhost:8080/api/genai/v1/analyze/health
```

## 🔍 Troubleshooting

### Common Issues

**API not starting**:
- Check Docker containers: `docker-compose ps`
- View logs: `docker-compose logs api`
- Verify environment variables

**Processing failures**:
- Check worker logs: `docker-compose logs worker`
- Verify input file accessibility
- Check storage backend connectivity

**GenAI not working**:
- Verify GENAI_ENABLED=true
- Check GPU availability: `nvidia-smi`
- Ensure AI models are downloaded
- Check GenAI logs: `docker-compose logs worker-genai`

**Storage issues**:
- Verify storage backend credentials
- Check network connectivity to storage service
- Confirm file permissions

### Performance Issues
- Monitor system resources via Grafana
- Scale workers if queue is backing up
- Check storage I/O performance
- Monitor GPU utilization (if using GenAI)

## 📚 API Documentation

### Interactive Documentation
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc
- **OpenAPI JSON**: http://localhost:8080/openapi.json

### Response Formats
All API responses follow a consistent format:
```json
{
  "job_id": "uuid",
  "status": "processing|completed|failed",
  "progress": 0.0-100.0,
  "result": {},
  "error": null,
  "created_at": "2025-07-03T10:00:00Z",
  "updated_at": "2025-07-03T10:01:00Z"
}
```

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

### Development Guidelines
- Follow PEP 8 coding standards
- Add type hints to new code
- Update documentation for new features
- Ensure all tests pass
- Add integration tests for new endpoints

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related Projects

- **FFmpeg**: The core video processing engine
- **Real-ESRGAN**: AI video upscaling
- **PySceneDetect**: Scene boundary detection
- **VMAF**: Video quality assessment

## 💬 Support

- **Documentation**: Available in `/docs` directory
- **Issues**: GitHub Issues for bug reports
- **Discussions**: GitHub Discussions for questions
- **Email**: dev@rendiff.dev

## 🗺️ Roadmap

### Upcoming Features
- **Audio AI Enhancement**: AI-powered audio processing
- **Live Streaming**: Real-time video processing
- **Advanced Analytics**: Machine learning-based insights
- **Cloud Integration**: Native cloud provider integrations
- **WebUI**: Web-based management interface

---

**Made with ❤️ by the Rendiff team**
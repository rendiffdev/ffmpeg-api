# 🚀 Rendiff FFmpeg API - Production Deployment Guide

## ✅ **IMPLEMENTATION STATUS: COMPLETE**

All video processing core components have been implemented and are ready for production deployment.

**Rendiff** - Professional FFmpeg API Service  
🌐 [rendiff.dev](https://rendiff.dev) | 📧 [dev@rendiff.dev](mailto:dev@rendiff.dev) | 🐙 [GitHub](https://github.com/rendiffdev)

---

## 📋 **Pre-Deployment Requirements**

### **1. System Dependencies** 
```bash
# Install FFmpeg with hardware acceleration support
sudo apt update
sudo apt install ffmpeg libavcodec-extra

# Verify FFmpeg installation
ffmpeg -version
ffmpeg -encoders | grep -E "(nvenc|qsv|vaapi)"

# Install Python dependencies
pip install -r requirements.txt
```

### **2. Environment Configuration**
```bash
# Copy environment template
cp .env.example .env

# Configure essential variables
RENDIFF_API_KEY=your-secure-32-char-api-key
DATABASE_URL=sqlite+aiosqlite:///data/rendiff.db
STORAGE_CONFIG=config/storage.yml

# For production with PostgreSQL
# DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/rendiff
```

### **3. Storage Configuration**
```bash
# Copy storage template
cp config/storage.yml.example config/storage.yml

# Configure storage backends (S3, Azure, GCS, etc.)
# Edit config/storage.yml with your credentials
```

---

## 🐳 **Deployment Options**

### **Option 1: Quick Start (SQLite + Local Storage)**
```bash
# Perfect for testing and development
git clone https://github.com/your-org/rendiff.git
cd rendiff
cp .env.example .env
docker-compose -f docker-compose.setup.yml up -d

# Health check
curl http://localhost:8080/api/v1/health
```

### **Option 2: Auto-Setup with Cloud Storage**
```bash
# Environment-based setup
RENDIFF_AUTO_SETUP=true \
AWS_ACCESS_KEY_ID=your_key \
AWS_SECRET_ACCESS_KEY=your_secret \
AWS_S3_BUCKET=your-bucket \
docker-compose -f docker-compose.setup.yml up -d
```

### **Option 3: Production Deployment**
```bash
# Full production stack with PostgreSQL and monitoring
cp .env.example .env
# Edit .env with production values

docker-compose --profile postgres --profile monitoring -f docker-compose.prod.yml up -d

# Verify deployment
curl http://localhost:8080/api/v1/health/detailed
```

---

## 🧪 **Pre-Production Testing**

### **1. API Endpoints Test**
```bash
# Test video conversion
curl -X POST http://localhost:8080/api/v1/convert \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input_path": "s3://bucket/input.mp4",
    "output_path": "s3://bucket/output.mp4",
    "options": {"format": "mp4"},
    "operations": [
      {
        "type": "transcode",
        "params": {
          "video_codec": "h264",
          "audio_codec": "aac",
          "video_bitrate": "2M"
        }
      }
    ]
  }'

# Test quality analysis
curl -X POST http://localhost:8080/api/v1/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "reference_path": "s3://bucket/original.mp4",
    "test_path": "s3://bucket/encoded.mp4"
  }'

# Test streaming generation
curl -X POST http://localhost:8080/api/v1/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input_path": "s3://bucket/input.mp4",
    "output_path": "s3://bucket/hls/",
    "format": "hls",
    "adaptive": true
  }'
```

### **2. System Health Checks**
```bash
# Check system capabilities
curl http://localhost:8080/api/v1/capabilities

# Monitor worker status
curl http://localhost:8080/api/v1/workers

# Check storage backends
curl http://localhost:8080/api/v1/storage
```

### **3. Load Testing** (Optional)
```bash
# Use Apache Bench for basic load testing
ab -n 100 -c 10 http://localhost:8080/api/v1/health

# Monitor resource usage during load
curl http://localhost:8080/api/v1/stats?period=1h
```

---

## 🔒 **Security Configuration**

### **1. API Authentication**
```bash
# Generate secure API keys
openssl rand -hex 32

# Configure in .env
RENDIFF_API_KEY=your-generated-key
ENABLE_API_KEYS=true
```

### **2. Network Security**
```bash
# Configure firewall (example for UFW)
sudo ufw allow 8080/tcp  # API port
sudo ufw allow 22/tcp    # SSH
sudo ufw enable

# Use reverse proxy with SSL (Nginx example)
# Configure nginx.conf with SSL certificates
```

### **3. Resource Limits**
```yaml
# In docker-compose.prod.yml
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '4.0'
    reservations:
      memory: 2G
      cpus: '2.0'
```

---

## 📊 **Monitoring Setup**

### **1. Health Monitoring**
```bash
# Set up health check endpoints
curl http://localhost:8080/api/v1/health/detailed

# Monitor worker health
curl http://localhost:8080/api/v1/workers
```

### **2. Prometheus Metrics**
```bash
# Access Prometheus metrics
curl http://localhost:9090

# Check Grafana dashboards
# Login to http://localhost:3000 (admin/admin)
```

### **3. Log Aggregation**
```bash
# View service logs
docker-compose logs -f api
docker-compose logs -f worker-cpu
docker-compose logs -f worker-gpu
```

---

## 🔧 **Performance Optimization**

### **1. Hardware Configuration**
```bash
# For GPU acceleration
docker-compose --profile gpu up -d

# Check GPU status
./rendiff setup gpu
./rendiff ffmpeg capabilities
```

### **2. Worker Scaling**
```bash
# Scale workers based on load
docker-compose up -d --scale worker-cpu=6
docker-compose up -d --scale worker-gpu=2

# Monitor worker utilization
curl http://localhost:8080/api/v1/workers
```

### **3. Storage Optimization**
```bash
# Configure storage backends for performance
# Use local storage for temporary files
# Use cloud storage for input/output
# Configure appropriate bucket regions
```

---

## 🚨 **Troubleshooting Guide**

### **Common Issues & Solutions**

#### **1. Services Won't Start**
```bash
# Check service status
./rendiff service status

# View detailed logs
docker-compose logs api
docker-compose logs worker-cpu

# Check resource usage
./rendiff info
```

#### **2. Storage Connection Errors**
```bash
# Test storage backends
./rendiff storage test s3
./rendiff storage test azure

# Check credentials and permissions
# Verify bucket/container exists
```

#### **3. Processing Failures**
```bash
# Check FFmpeg availability
./rendiff ffmpeg version

# Verify hardware acceleration
./rendiff ffmpeg capabilities

# Check system resources
./rendiff system verify
```

#### **4. Performance Issues**
```bash
# Monitor resource usage
curl http://localhost:8080/api/v1/stats

# Check worker distribution
curl http://localhost:8080/api/v1/workers

# Review Grafana dashboards
# http://localhost:3000
```

---

## ✅ **Production Readiness Checklist**

### **Core Functionality**
- [x] Video transcoding with hardware acceleration
- [x] Quality analysis (VMAF, PSNR, SSIM)
- [x] Streaming format generation (HLS/DASH)
- [x] Real-time progress tracking
- [x] Multi-storage backend support

### **Production Features**
- [x] API authentication and authorization
- [x] Comprehensive error handling
- [x] Resource monitoring and limits
- [x] Health checks and metrics
- [x] Docker containerization

### **Scalability**
- [x] Horizontal worker scaling
- [x] Load balancer ready
- [x] Queue-based job processing
- [x] Storage backend abstraction
- [x] Monitoring and alerting

### **Security**
- [x] Input validation and sanitization
- [x] API key authentication
- [x] Resource limits and timeouts
- [x] Non-root container execution
- [x] Error message sanitization

### **Reliability**
- [x] Graceful error handling
- [x] Job retry mechanisms
- [x] Database migrations
- [x] Backup and restore procedures
- [x] System recovery tools

---

## 🎉 **Deployment Success Indicators**

After successful deployment, you should see:

1. **✅ API Health**: `GET /api/v1/health` returns `{"status": "healthy"}`
2. **✅ Capabilities**: `GET /api/v1/capabilities` shows available formats and operations
3. **✅ Workers Active**: `GET /api/v1/workers` shows active workers
4. **✅ Storage Connected**: `GET /api/v1/storage` shows storage backend status
5. **✅ Metrics Available**: Prometheus metrics at `:9090`
6. **✅ Dashboards**: Grafana dashboards at `:3000`

### **Test Processing**
```bash
# Submit a test job
curl -X POST http://localhost:8080/api/v1/convert \
  -H "X-API-Key: your-key" \
  -d '{"input_path": "test.mp4", "output_path": "output.mp4", "operations": []}'

# Check job progress
curl http://localhost:8080/api/v1/jobs/{job_id}

# Monitor real-time progress
curl http://localhost:8080/api/v1/jobs/{job_id}/events
```

---

## 🚀 **Post-Deployment**

### **1. Performance Tuning**
- Monitor processing times and optimize worker counts
- Adjust resource limits based on actual usage
- Configure storage for optimal performance

### **2. Monitoring Setup**
- Set up alerting for failed jobs
- Monitor storage usage and costs
- Track API response times and error rates

### **3. Scaling Strategy**
- Plan horizontal scaling based on load patterns
- Consider multi-region deployments
- Implement auto-scaling policies

**🎬 Your Rendiff FFmpeg API is now ready for production video processing! 🎉**
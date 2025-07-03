#!/bin/bash
# Rendiff FFmpeg API - Production Deployment Script

set -e

echo "🚀 Rendiff FFmpeg API - Production Deployment"
echo "=============================================="

# Configuration
DEPLOY_TYPE=${1:-standard}
ENV_FILE=${2:-.env}

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Environment file $ENV_FILE not found"
    echo "📝 Please copy .env.example to .env and configure it"
    echo "   cp .env.example .env"
    exit 1
fi

# Load environment variables
set -a
source "$ENV_FILE"
set +a

echo "📋 Deployment Configuration:"
echo "   Type: $DEPLOY_TYPE"
echo "   Environment: $ENV_FILE"
echo "   Storage Backend: ${STORAGE_BACKEND:-local}"
echo "   GenAI Enabled: ${GENAI_ENABLED:-false}"

# Validate configuration
if [ "$DEPLOY_TYPE" = "genai" ] && [ "${GENAI_ENABLED:-false}" != "true" ]; then
    echo "❌ GenAI deployment requested but GENAI_ENABLED is not true"
    echo "   Please set GENAI_ENABLED=true in your .env file"
    exit 1
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed"
    exit 1
fi

# Check GPU requirements for GenAI
if [ "$DEPLOY_TYPE" = "genai" ]; then
    echo "🔍 Checking GPU requirements for GenAI deployment..."
    
    if ! command -v nvidia-smi &> /dev/null; then
        echo "⚠️ nvidia-smi not found. GPU acceleration may not be available."
    else
        echo "✅ NVIDIA GPU detected:"
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits | head -1
    fi
    
    # Check for NVIDIA Container Runtime
    if ! docker info | grep -q nvidia; then
        echo "⚠️ NVIDIA Container Runtime not detected"
        echo "   GenAI features will fall back to CPU (slower performance)"
    fi
fi

# Create required directories
echo "📁 Creating required directories..."
mkdir -p ./storage ./models/genai ./logs

# Pull latest images
echo "🐳 Pulling Docker images..."
if [ "$DEPLOY_TYPE" = "genai" ]; then
    docker-compose -f docker-compose.genai.yml pull
else
    docker-compose pull
fi

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose down 2>/dev/null || true
if [ "$DEPLOY_TYPE" = "genai" ]; then
    docker-compose -f docker-compose.genai.yml down 2>/dev/null || true
fi

# Deploy based on type
if [ "$DEPLOY_TYPE" = "genai" ]; then
    echo "🤖 Deploying with GenAI features..."
    
    # Download AI models if needed
    if [ ! -d "./models/genai" ] || [ -z "$(ls -A ./models/genai)" ]; then
        echo "📥 Downloading AI models (this may take a while)..."
        docker-compose -f docker-compose.yml -f docker-compose.genai.yml --profile setup up model-downloader
    fi
    
    # Start GenAI-enabled services (migrations run automatically)
    docker-compose -f docker-compose.yml -f docker-compose.genai.yml up -d
    
    echo "✅ GenAI deployment complete!"
    echo "🌐 API: http://localhost:8080"
    echo "📊 Docs: http://localhost:8080/docs"
    echo "🤖 GenAI: http://localhost:8080/api/genai/v1/"
    echo "📈 Monitoring: http://localhost:3000"
    
else
    echo "🎬 Deploying standard FFmpeg API..."
    
    # Start standard services (migrations run automatically)
    docker-compose up -d
    
    echo "✅ Standard deployment complete!"
    echo "🌐 API: http://localhost:8080"
    echo "📊 Docs: http://localhost:8080/docs"
    echo "📈 Monitoring: http://localhost:3000"
fi

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Health check
echo "🏥 Performing health check..."
if curl -s "http://localhost:8080/api/v1/health" > /dev/null; then
    echo "✅ API is healthy and ready!"
else
    echo "❌ API health check failed"
    echo "📋 Check logs: docker-compose logs api"
    exit 1
fi

# GenAI health check
if [ "$DEPLOY_TYPE" = "genai" ]; then
    if curl -s "http://localhost:8080/api/genai/v1/analyze/health" > /dev/null; then
        echo "✅ GenAI services are healthy!"
    else
        echo "⚠️ GenAI health check failed (services may still be initializing)"
        echo "📋 Check logs: docker-compose logs worker-genai"
    fi
fi

echo ""
echo "🎉 Deployment successful!"
echo ""
echo "📚 Next steps:"
echo "   • View API documentation: http://localhost:8080/docs"
echo "   • Monitor system: http://localhost:3000"
echo "   • View logs: docker-compose logs -f"
echo "   • Scale workers: docker-compose up -d --scale worker=4"
if [ "$DEPLOY_TYPE" = "genai" ]; then
    echo "   • Scale AI workers: docker-compose -f docker-compose.genai.yml up -d --scale worker-genai=2"
fi
echo ""
echo "🔧 Management commands:"
echo "   • Update: ./deploy.sh $DEPLOY_TYPE"
echo "   • Stop: docker-compose down"
echo "   • View status: docker-compose ps"
#!/bin/bash

# Rendiff FFmpeg API - Simple Setup Script
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "🚀 Rendiff FFmpeg API Setup"
echo "=========================="

# Function to show usage
show_usage() {
    echo "Usage: $0 [--development|--standard|--genai|--status|--stop]"
    echo ""
    echo "Options:"
    echo "  --development    Quick local development setup (SQLite, no auth)"
    echo "  --standard       Production setup (PostgreSQL, Redis, auth)"
    echo "  --genai          AI-enhanced setup (GPU support)"
    echo "  --status         Show current status"
    echo "  --stop           Stop all services"
    echo "  --help           Show this help"
    exit 1
}

# Function to check requirements
check_requirements() {
    echo "Checking requirements..."
    
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
        echo "❌ Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi
    
    echo "✅ Docker and Docker Compose are available"
}

# Function for development setup
setup_development() {
    echo "🛠️  Setting up Development Environment..."
    
    # Create development .env file
    cat > .env << EOF
# Development Configuration
DATABASE_URL=sqlite+aiosqlite:///data/rendiff.db
REDIS_URL=redis://redis:6379/0
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true
LOG_LEVEL=debug
STORAGE_PATH=./storage
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
ENABLE_API_KEYS=false
POSTGRES_PASSWORD=dev_password_123
GRAFANA_PASSWORD=admin
EOF

    # Create minimal docker-compose for development
    cat > docker-compose.dev.yml << EOF
services:
  # Redis for queue
  redis:
    image: redis:7-alpine
    container_name: ffmpeg_dev_redis
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_dev_data:/data

  # Simple API service
  api:
    build:
      context: .
      dockerfile: docker/api/Dockerfile
    container_name: ffmpeg_dev_api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///data/rendiff.db
      - REDIS_URL=redis://redis:6379/0
      - DEBUG=true
      - ENABLE_API_KEYS=false
    volumes:
      - ./storage:/storage
      - ./data:/data
    depends_on:
      - redis
    command: python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  redis_dev_data:
EOF

    echo "📁 Creating directories..."
    mkdir -p storage data logs

    echo "🐳 Starting development services..."
    docker compose -f docker-compose.dev.yml up -d

    echo ""
    echo "✅ Development setup complete!"
    echo ""
    echo "🌐 API available at: http://localhost:8000"
    echo "📚 API docs at: http://localhost:8000/docs"
    echo "🔍 Health check: http://localhost:8000/api/v1/health"
    echo ""
    echo "📝 To stop: ./setup.sh --stop"
}

# Function to show status
show_status() {
    echo "📊 Current Status:"
    echo "=================="
    
    if docker compose -f docker-compose.dev.yml ps 2>/dev/null | grep -q "Up"; then
        echo "🟢 Development environment is running"
        docker compose -f docker-compose.dev.yml ps
        echo ""
        echo "🌐 Access URLs:"
        echo "   API: http://localhost:8000"
        echo "   Docs: http://localhost:8000/docs"
    else
        echo "🔴 Development environment is not running"
    fi
}

# Function to stop services
stop_services() {
    echo "🛑 Stopping services..."
    
    if [ -f "docker-compose.dev.yml" ]; then
        docker compose -f docker-compose.dev.yml down
    fi
    
    echo "✅ Services stopped"
}

# Parse command line arguments
case "${1:-}" in
    --development|--dev)
        check_requirements
        setup_development
        ;;
    --standard|--prod)
        echo "🚧 Standard/Production setup not implemented yet"
        echo "💡 Use --development for now"
        exit 1
        ;;
    --genai|--ai)
        echo "🚧 GenAI setup not implemented yet"
        echo "💡 Use --development for now"
        exit 1
        ;;
    --status)
        show_status
        ;;
    --stop)
        stop_services
        ;;
    --help|-h)
        show_usage
        ;;
    *)
        echo "❌ Unknown option: ${1:-}"
        show_usage
        ;;
esac
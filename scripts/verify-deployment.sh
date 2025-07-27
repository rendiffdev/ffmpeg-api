#\!/bin/bash
# Comprehensive deployment verification script

set -e

echo "🔍 FFmpeg API Deployment Verification"
echo "====================================="

# Check required files
echo "📋 Checking required files..."

REQUIRED_FILES=(
    "compose.yml"
    "docker-compose.genai.yml"
    ".env.example"
    "requirements.txt"
    "requirements-genai.txt"
    "docker/api/Dockerfile"
    "docker/worker/Dockerfile"
    "docker/api/Dockerfile.genai"
    "docker/worker/Dockerfile.genai"
    "docker/install-ffmpeg.sh"
    "docker/postgres/init/01-init-db.sql"
    "docker/postgres/init/02-create-schema.sql"
    "docker/redis/redis.conf"
    "scripts/docker-entrypoint.sh"
    "scripts/health-check.sh"
    "deploy.sh"
    "alembic/versions/001_initial_schema.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ Missing: $file"
        exit 1
    fi
done

# Check directory structure
echo "📁 Checking directory structure..."

REQUIRED_DIRS=(
    "api"
    "worker"
    "storage"
    "config"
    "docker/api"
    "docker/worker"
    "docker/postgres/init"
    "docker/redis"
    "scripts"
    "alembic/versions"
    "monitoring"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "✅ $dir/"
    else
        echo "❌ Missing directory: $dir/"
        exit 1
    fi
done

# Check executable permissions
echo "🔐 Checking executable permissions..."

EXECUTABLE_FILES=(
    "deploy.sh"
    "docker/install-ffmpeg.sh"
    "scripts/docker-entrypoint.sh"
    "scripts/health-check.sh"
)

for file in "${EXECUTABLE_FILES[@]}"; do
    if [ -x "$file" ]; then
        echo "✅ $file (executable)"
    else
        echo "❌ Not executable: $file"
        chmod +x "$file"
        echo "🔧 Fixed permissions for $file"
    fi
done

# Check Docker Compose syntax
echo "🐳 Validating Docker Compose files..."

if docker-compose config >/dev/null 2>&1; then
    echo "✅ compose.yml syntax is valid"
else
    echo "❌ compose.yml has syntax errors"
    exit 1
fi

if docker-compose -f compose.yml -f docker-compose.genai.yml config >/dev/null 2>&1; then
    echo "✅ docker-compose.genai.yml syntax is valid"
else
    echo "❌ docker-compose.genai.yml has syntax errors"
    exit 1
fi

# Check environment template
echo "🔧 Checking environment template..."

if grep -q "DATABASE_URL=postgresql" .env.example; then
    echo "✅ PostgreSQL configuration in .env.example"
else
    echo "❌ Missing PostgreSQL configuration in .env.example"
    exit 1
fi

if grep -q "REDIS_URL=redis" .env.example; then
    echo "✅ Redis configuration in .env.example"
else
    echo "❌ Missing Redis configuration in .env.example"
    exit 1
fi

# Check database initialization scripts
echo "🗃️ Checking database scripts..."

if grep -q "CREATE TABLE.*jobs" docker/postgres/init/02-create-schema.sql; then
    echo "✅ Database schema includes jobs table"
else
    echo "❌ Missing jobs table in database schema"
    exit 1
fi

if grep -q "CREATE EXTENSION.*uuid-ossp" docker/postgres/init/01-init-db.sql; then
    echo "✅ UUID extension setup in database init"
else
    echo "❌ Missing UUID extension in database init"
    exit 1
fi

# Check Redis configuration
echo "📮 Checking Redis configuration..."

if grep -q "maxmemory.*gb" docker/redis/redis.conf; then
    echo "✅ Redis memory configuration"
else
    echo "❌ Missing Redis memory configuration"
    exit 1
fi

# Check dependencies
echo "📦 Checking Python dependencies..."

if grep -q "asyncpg" requirements.txt; then
    echo "✅ PostgreSQL async driver in requirements"
else
    echo "❌ Missing PostgreSQL driver in requirements"
    exit 1
fi

if grep -q "redis" requirements.txt; then
    echo "✅ Redis client in requirements"
else
    echo "❌ Missing Redis client in requirements"
    exit 1
fi

if [ -f "requirements-genai.txt" ]; then
    if grep -q "torch" requirements-genai.txt; then
        echo "✅ PyTorch in GenAI requirements"
    else
        echo "❌ Missing PyTorch in GenAI requirements"
        exit 1
    fi
fi

# Check documentation
echo "📚 Checking documentation..."

if grep -q "Zero-Configuration Setup" README.md; then
    echo "✅ README mentions zero-config setup"
else
    echo "❌ README missing zero-config information"
    exit 1
fi

if grep -q "PostgreSQL.*auto-configured" README.md; then
    echo "✅ README mentions auto-configured PostgreSQL"
else
    echo "❌ README missing PostgreSQL auto-config information"
    exit 1
fi

# Final summary
echo ""
echo "🎉 Deployment Verification Complete\!"
echo "======================================"
echo ""
echo "✅ All required files present"
echo "✅ Directory structure correct"
echo "✅ Executable permissions set"
echo "✅ Docker Compose syntax valid"
echo "✅ Environment configuration complete"
echo "✅ Database initialization ready"
echo "✅ Redis configuration optimized"
echo "✅ Dependencies properly configured"
echo "✅ Documentation updated"
echo ""
echo "🚀 Repository is ready for GitHub push\!"
echo ""
echo "📋 Deployment Summary:"
echo "   • PostgreSQL 15 - Fully automated setup"
echo "   • Redis 7 - Production optimized"
echo "   • FFmpeg - Latest version with all codecs"
echo "   • Health checks - Comprehensive monitoring"
echo "   • Auto-migrations - Zero manual setup"
echo "   • GenAI support - Optional GPU acceleration"
echo ""
echo "🔥 Quick start commands:"
echo "   Standard: docker-compose up -d"
echo "   With AI:  docker-compose -f docker-compose.genai.yml up -d"
echo "   Deploy:   ./deploy.sh standard"
EOF < /dev/null
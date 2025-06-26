#!/bin/bash
set -e

# Rendiff Docker Entry Point
# Handles first-run setup and service initialization

SETUP_MARKER="/data/.rendiff_setup_complete"
CONFIG_DIR="/config"
DATA_DIR="/data"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Ensure required directories exist
create_directories() {
    log_info "Creating required directories..."
    mkdir -p "$CONFIG_DIR" "$DATA_DIR" "/storage" "/tmp/rendiff"
    
    # Set proper permissions
    chown -R rendiff:rendiff "$CONFIG_DIR" "$DATA_DIR" "/storage" "/tmp/rendiff" 2>/dev/null || true
}

# Check if this is the first run
is_first_run() {
    if [[ ! -f "$SETUP_MARKER" ]]; then
        return 0  # First run
    else
        return 1  # Not first run
    fi
}

# Check if running in interactive mode
is_interactive() {
    if [[ -t 0 && -t 1 ]]; then
        return 0  # Interactive
    else
        return 1  # Non-interactive
    fi
}

# Auto-setup with environment variables
auto_setup() {
    log_info "Running automatic setup with environment variables..."
    
    # Create basic configuration from environment
    cat > "$CONFIG_DIR/storage.yml" << EOF
version: "1.0.0"
storage:
  default_backend: "${STORAGE_DEFAULT_BACKEND:-local}"
  backends:
    local:
      name: "local"
      type: "filesystem"
      base_path: "${STORAGE_LOCAL_PATH:-/storage}"
      permissions: "0755"
  policies:
    input_backends: ["${STORAGE_INPUT_BACKENDS:-local}"]
    output_backends: ["${STORAGE_OUTPUT_BACKENDS:-local}"]
    retention:
      default: "${STORAGE_RETENTION:-7d}"
EOF

    # Create environment file
    cat > "$CONFIG_DIR/.env" << EOF
# Rendiff Configuration - Auto-generated
API_HOST=${API_HOST:-0.0.0.0}
API_PORT=${API_PORT:-8080}
API_WORKERS=${API_WORKERS:-4}
EXTERNAL_URL=${EXTERNAL_URL:-http://localhost:8080}

STORAGE_CONFIG=/config/storage.yml

MAX_UPLOAD_SIZE=${MAX_UPLOAD_SIZE:-10737418240}
MAX_CONCURRENT_JOBS_PER_KEY=${MAX_CONCURRENT_JOBS_PER_KEY:-10}

ENABLE_API_KEYS=${ENABLE_API_KEYS:-true}
EOF

    # Add cloud storage if configured
    if [[ -n "$AWS_ACCESS_KEY_ID" && -n "$AWS_SECRET_ACCESS_KEY" && -n "$AWS_S3_BUCKET" ]]; then
        log_info "Configuring AWS S3 storage..."
        
        # Add S3 backend to storage config
        cat >> "$CONFIG_DIR/storage.yml" << EOF
    s3:
      name: "s3"
      type: "s3"
      endpoint: "${AWS_S3_ENDPOINT:-https://s3.amazonaws.com}"
      region: "${AWS_S3_REGION:-us-east-1}"
      bucket: "$AWS_S3_BUCKET"
      access_key: "\${AWS_ACCESS_KEY_ID}"
      secret_key: "\${AWS_SECRET_ACCESS_KEY}"
      path_style: ${AWS_S3_PATH_STYLE:-false}
EOF
        
        # Add environment variables
        cat >> "$CONFIG_DIR/.env" << EOF

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
AWS_S3_BUCKET=$AWS_S3_BUCKET
AWS_S3_REGION=${AWS_S3_REGION:-us-east-1}
EOF
    fi

    # Add Azure storage if configured
    if [[ -n "$AZURE_STORAGE_ACCOUNT" && -n "$AZURE_STORAGE_KEY" && -n "$AZURE_CONTAINER" ]]; then
        log_info "Configuring Azure Blob Storage..."
        
        cat >> "$CONFIG_DIR/storage.yml" << EOF
    azure:
      name: "azure"
      type: "azure"
      account_name: "$AZURE_STORAGE_ACCOUNT"
      container: "$AZURE_CONTAINER"
      account_key: "\${AZURE_STORAGE_KEY}"
EOF
        
        cat >> "$CONFIG_DIR/.env" << EOF

# Azure Storage Configuration
AZURE_STORAGE_ACCOUNT=$AZURE_STORAGE_ACCOUNT
AZURE_STORAGE_KEY=$AZURE_STORAGE_KEY
AZURE_CONTAINER=$AZURE_CONTAINER
EOF
    fi

    # Add GCS if configured
    if [[ -n "$GCP_PROJECT_ID" && -n "$GCS_BUCKET" && -f "/config/gcp-key.json" ]]; then
        log_info "Configuring Google Cloud Storage..."
        
        cat >> "$CONFIG_DIR/storage.yml" << EOF
    gcs:
      name: "gcs"
      type: "gcs"
      project_id: "$GCP_PROJECT_ID"
      bucket: "$GCS_BUCKET"
      credentials_file: "/config/gcp-key.json"
EOF
        
        cat >> "$CONFIG_DIR/.env" << EOF

# GCS Configuration
GCP_PROJECT_ID=$GCP_PROJECT_ID
GCS_BUCKET=$GCS_BUCKET
GOOGLE_APPLICATION_CREDENTIALS=/config/gcp-key.json
EOF
    fi

    # Generate API keys if enabled
    if [[ "${ENABLE_API_KEYS:-true}" == "true" ]]; then
        log_info "Generating API keys..."
        
        API_KEY=${RENDIFF_API_KEY:-$(openssl rand -base64 32)}
        
        cat > "$CONFIG_DIR/api_keys.json" << EOF
{
  "api_keys": [
    {
      "name": "default",
      "key": "$API_KEY",
      "role": "admin",
      "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    }
  ]
}
EOF
        chmod 600 "$CONFIG_DIR/api_keys.json"
        
        echo ""
        log_success "=== SETUP COMPLETE ==="
        log_success "Your Rendiff API key: $API_KEY"
        log_warning "Save this key securely - it won't be shown again!"
        echo ""
    fi
}

# Interactive setup using the wizard
interactive_setup() {
    log_info "Starting interactive setup wizard..."
    
    # Check if Python and wizard are available
    if command -v python3 >/dev/null 2>&1 && [[ -f "/app/setup/wizard.py" ]]; then
        cd /app
        python3 setup/wizard.py
    else
        log_error "Setup wizard not available. Falling back to auto-setup..."
        auto_setup
    fi
}

# Initialize database
init_database() {
    log_info "Initializing database..."
    
    if [[ -f "/app/scripts/init-db.py" ]]; then
        cd /app
        python3 scripts/init-db.py
    else
        log_warning "Database initialization script not found"
    fi
}

# Test system components
test_system() {
    log_info "Testing system components..."
    
    # Test FFmpeg
    if command -v ffmpeg >/dev/null 2>&1; then
        log_success "FFmpeg is available"
    else
        log_error "FFmpeg not found!"
        exit 1
    fi
    
    # Test storage paths
    if [[ -d "/storage" ]]; then
        log_success "Storage directory is accessible"
    else
        log_warning "Storage directory not mounted"
    fi
    
    # Test Python dependencies
    if python3 -c "import fastapi, celery, ffmpeg" 2>/dev/null; then
        log_success "Python dependencies are available"
    else
        log_error "Missing Python dependencies!"
        exit 1
    fi
}

# Mark setup as complete
mark_setup_complete() {
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$SETUP_MARKER"
    log_success "Setup marked as complete"
}

# Wait for database to be ready (if using external DB)
wait_for_database() {
    if [[ -n "$DATABASE_URL" && "$DATABASE_URL" != *"sqlite"* ]]; then
        log_info "Waiting for database to be ready..."
        
        # Extract database info from URL
        DB_HOST=$(echo "$DATABASE_URL" | sed -E 's/.*@([^:]+).*/\1/')
        DB_PORT=$(echo "$DATABASE_URL" | sed -E 's/.*:([0-9]+)\/.*/\1/')
        
        if command -v nc >/dev/null 2>&1; then
            for i in {1..30}; do
                if nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; then
                    log_success "Database is ready"
                    return 0
                fi
                log_info "Waiting for database... ($i/30)"
                sleep 2
            done
            log_error "Database not ready after 60 seconds"
            exit 1
        fi
    fi
}

# Main setup flow
main_setup() {
    log_info "=== Rendiff Setup Starting ==="
    
    create_directories
    test_system
    wait_for_database
    
    if is_first_run; then
        log_info "First run detected - starting setup process"
        
        # Determine setup mode
        if [[ "${RENDIFF_AUTO_SETUP:-false}" == "true" ]] || ! is_interactive; then
            log_info "Running in automatic setup mode"
            auto_setup
        else
            log_info "Running in interactive setup mode"
            interactive_setup
        fi
        
        init_database
        mark_setup_complete
        
        log_success "=== Setup Complete ==="
        echo ""
        log_info "Rendiff is now configured and ready to use!"
        log_info "API will be available at: ${EXTERNAL_URL:-http://localhost:8080}"
        echo ""
    else
        log_info "System already configured - skipping setup"
    fi
}

# Handle different service types
case "${1:-api}" in
    "api")
        main_setup
        log_info "Starting Rendiff API server..."
        exec python3 -m api.main
        ;;
    "worker")
        # Workers don't need setup, just wait for API to be ready
        log_info "Starting Rendiff Worker..."
        
        # Wait for API to be ready
        API_URL="${EXTERNAL_URL:-http://localhost:8080}/api/v1/health"
        for i in {1..30}; do
            if curl -s "$API_URL" >/dev/null 2>&1; then
                break
            fi
            log_info "Waiting for API to be ready... ($i/30)"
            sleep 2
        done
        
        exec python3 -m worker.main
        ;;
    "setup")
        # Force setup mode
        rm -f "$SETUP_MARKER"
        main_setup
        ;;
    "shell")
        # Debug shell
        exec /bin/bash
        ;;
    *)
        # Custom command
        exec "$@"
        ;;
esac
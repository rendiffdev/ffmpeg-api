#!/bin/bash

# Rendiff FFmpeg API - Unified Setup Script
# Single entry point for all deployment types

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="Rendiff FFmpeg API"
VERSION="1.0.0"

# Print colored output
print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                    ${PROJECT_NAME}                    ║${NC}"
    echo -e "${BLUE}║                    Unified Setup v${VERSION}                     ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${CYAN}ℹ $1${NC}"; }

# Show usage information
show_usage() {
    cat << EOF
Usage: ./setup.sh [OPTION]

DEPLOYMENT OPTIONS:
  --development, -d     Quick development setup (SQLite, local storage)
  --production, -p      Production setup with interactive configuration
  --standard, -s        Standard production deployment (PostgreSQL, Redis)
  --genai, -g          GenAI-enabled deployment (GPU support, AI features)
  --interactive, -i     Interactive setup wizard (recommended for first-time)
  
MANAGEMENT OPTIONS:
  --validate, -v        Validate current configuration
  --status              Show deployment status
  --help, -h           Show this help message

EXAMPLES:
  ./setup.sh --development          # Quick dev setup
  ./setup.sh --production           # Production with wizard
  ./setup.sh --standard             # Standard production
  ./setup.sh --genai                # AI-enabled production
  ./setup.sh --interactive          # Full interactive setup

For detailed documentation, see: docs/SETUP.md
EOF
}

# Install Docker
install_docker() {
    print_info "Installing Docker and Docker Compose..."
    
    # Update package index
    sudo apt-get update
    
    # Install required packages
    sudo apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Add Docker's official GPG key
    sudo mkdir -m 0755 -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # Set up the repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Update package index with Docker packages
    sudo apt-get update
    
    # Install Docker Engine and Docker Compose
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Add current user to docker group
    sudo usermod -aG docker $USER
    
    print_success "Docker and Docker Compose installed successfully!"
    print_warning "Please log out and log back in for group changes to take effect."
    print_info "Or run: newgrp docker"
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_warning "Docker is not installed."
        echo -n "Would you like to install Docker and Docker Compose automatically? (y/N): "
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            install_docker
            print_info "Please restart your terminal session and run the script again."
            exit 0
        else
            print_error "Docker is required. Please install Docker Desktop manually."
            exit 1
        fi
    fi
    
    # Check Docker Compose
    if ! command -v docker compose &> /dev/null; then
        print_warning "Docker Compose is not installed."
        echo -n "Would you like to install Docker Compose automatically? (y/N): "
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            # Install Docker Compose plugin
            sudo apt-get update
            sudo apt-get install -y docker-compose-plugin
            print_success "Docker Compose installed successfully!"
        else
            print_error "Docker Compose is required. Please install Docker Compose manually."
            exit 1
        fi
    fi
    
    # Check Git (optional but recommended)
    if ! command -v git &> /dev/null; then
        print_warning "Git is not installed. Some features may not work optimally."
        echo -n "Would you like to install Git? (y/N): "
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            print_info "Installing Git..."
            sudo apt-get update
            sudo apt-get install -y git
            print_success "Git installed successfully!"
        else
            print_info "Continuing without Git. Some features may be limited."
        fi
    fi
    
    print_success "Prerequisites check completed"
}

# Development setup
setup_development() {
    print_info "Setting up development environment..."
    
    # Create minimal .env for development
    cat > .env << EOF
# Development Configuration - Auto-generated by setup.sh
DATABASE_URL=sqlite+aiosqlite:///data/rendiff.db
REDIS_URL=redis://redis:6379/0
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true
LOG_LEVEL=debug
STORAGE_PATH=./storage
CORS_ORIGINS=http://localhost,https://localhost
ENABLE_API_KEYS=false
EOF
    
    print_success "Development environment configured"
    print_info "Starting development services..."
    
    # Start development services
    docker compose up -d
    
    print_success "Development environment is running!"
    echo ""
    print_info "Access your API at: ${CYAN}http://localhost:8080${NC}"
    print_info "API Documentation: ${CYAN}http://localhost:8080/docs${NC}"
    print_info "Direct API: ${CYAN}http://localhost:8000${NC}"
}

# Standard production setup
setup_standard() {
    print_info "Setting up standard production environment..."
    
    # Generate secure passwords
    POSTGRES_PASSWORD=$(openssl rand -hex 16)
    GRAFANA_PASSWORD=$(openssl rand -hex 12)
    
    # Create production .env
    cat > .env << EOF
# Standard Production Configuration - Auto-generated by setup.sh
DATABASE_URL=postgresql://ffmpeg_user:${POSTGRES_PASSWORD}@postgres:5432/ffmpeg_api
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_USER=ffmpeg_user
POSTGRES_DB=ffmpeg_api
REDIS_URL=redis://redis:6379/0
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
LOG_LEVEL=info
STORAGE_PATH=./storage
CORS_ORIGINS=http://localhost,https://localhost
ENABLE_API_KEYS=true
GRAFANA_PASSWORD=${GRAFANA_PASSWORD}
CPU_WORKERS=2
GPU_WORKERS=0
MAX_UPLOAD_SIZE=10737418240
EOF
    
    # Generate API keys
    print_info "Generating API keys..."
    ./scripts/manage-api-keys.sh generate --count 3 --silent
    
    print_success "Standard production environment configured"
    print_info "Starting production services..."
    
    # Start production services with HTTPS by default
    docker compose -f docker compose.prod.yml up -d
    
    print_success "Standard production environment is running!"
    show_access_info
}

# GenAI-enabled setup
setup_genai() {
    print_info "Setting up GenAI-enabled environment..."
    
    # Check for GPU support
    if ! command -v nvidia-smi &> /dev/null; then
        print_warning "NVIDIA GPU drivers not detected. GenAI features may not work optimally."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Setup standard production first
    setup_standard
    
    # Add GenAI-specific configuration
    cat >> .env << EOF

# GenAI Configuration
GENAI_ENABLED=true
GENAI_GPU_ENABLED=true
GENAI_GPU_DEVICE=cuda:0
GENAI_MODEL_PATH=/app/models/genai
GPU_WORKERS=1
EOF
    
    print_info "Downloading AI models..."
    docker compose -f docker compose.yml -f docker compose.genai.yml --profile setup run --rm model-downloader
    
    print_info "Starting GenAI services..."
    docker compose -f docker compose.yml -f docker compose.genai.yml up -d
    
    print_success "GenAI environment is running!"
    show_access_info
    print_info "GenAI endpoints: ${CYAN}http://localhost:8080/api/genai/v1${NC}"
}

# Interactive setup wizard
setup_interactive() {
    print_info "Starting interactive setup wizard..."
    ./scripts/interactive-setup.sh
}

# Production setup with options
setup_production() {
    print_info "Starting production setup..."
    
    echo "Choose production configuration:"
    echo "1) Standard (PostgreSQL, Redis, Monitoring, Self-signed HTTPS)"
    echo "2) Standard + Let's Encrypt HTTPS"
    echo "3) GenAI-enabled (Self-signed HTTPS)"
    echo "4) GenAI + Let's Encrypt HTTPS"
    echo "5) Custom (interactive)"
    read -p "Enter choice (1-5): " choice
    
    case $choice in
        1) setup_standard ;;
        2) setup_standard_https ;;
        3) setup_genai ;;
        4) setup_genai_https ;;
        5) setup_interactive ;;
        *) print_error "Invalid choice" && exit 1 ;;
    esac
}

# Standard with HTTPS (Let's Encrypt)
setup_standard_https() {
    print_info "Setting up standard production with Let's Encrypt HTTPS..."
    
    # Check if domain is provided
    if [ "${DOMAIN_NAME:-localhost}" = "localhost" ]; then
        print_error "Let's Encrypt requires a valid domain. Please set DOMAIN_NAME environment variable."
        print_info "Example: export DOMAIN_NAME=api.yourdomain.com"
        exit 1
    fi
    
    setup_standard
    
    print_info "Configuring Let's Encrypt HTTPS..."
    ./scripts/enhanced-ssl-manager.sh setup-prod "$DOMAIN_NAME" "$CERTBOT_EMAIL"
    
    print_info "Restarting services with Let's Encrypt..."
    docker compose -f docker compose.prod.yml restart traefik
    
    print_success "HTTPS environment with Let's Encrypt is running!"
}

# GenAI with HTTPS (Let's Encrypt)
setup_genai_https() {
    print_info "Setting up GenAI with Let's Encrypt HTTPS..."
    
    # Check if domain is provided
    if [ "${DOMAIN_NAME:-localhost}" = "localhost" ]; then
        print_error "Let's Encrypt requires a valid domain. Please set DOMAIN_NAME environment variable."
        print_info "Example: export DOMAIN_NAME=api.yourdomain.com"
        exit 1
    fi
    
    setup_genai
    
    print_info "Configuring Let's Encrypt HTTPS..."
    ./scripts/enhanced-ssl-manager.sh setup-prod "$DOMAIN_NAME" "$CERTBOT_EMAIL"
    
    print_info "Restarting services with Let's Encrypt..."
    docker compose -f docker compose.yml -f docker compose.genai.yml down
    docker compose -f docker compose.prod.yml --profile genai up -d
    
    print_success "GenAI + HTTPS environment with Let's Encrypt is running!"
}

# Show access information
show_access_info() {
    echo ""
    print_success "Deployment completed successfully!"
    echo ""
    print_info "Access Information:"
    print_info "• API (HTTPS): ${CYAN}https://localhost${NC}"
    print_info "• API (HTTP - redirects to HTTPS): ${CYAN}http://localhost${NC}"
    print_info "• Documentation: ${CYAN}https://localhost/docs${NC}"
    print_info "• Health Check: ${CYAN}https://localhost/api/v1/health${NC}"
    print_info "• Monitoring: ${CYAN}http://localhost:3000${NC} (if enabled)"
    echo ""
    print_info "Management Commands:"
    print_info "• Check status: ${CYAN}./setup.sh --status${NC}"
    print_info "• Validate: ${CYAN}./setup.sh --validate${NC}"
    print_info "• View logs: ${CYAN}docker compose logs -f${NC}"
    echo ""
}

# Validate deployment
validate_deployment() {
    print_info "Validating deployment..."
    ./scripts/validate-production.sh
}

# Show deployment status
show_status() {
    print_info "Deployment Status:"
    docker compose ps
    
    echo ""
    print_info "Service Health:"
    ./scripts/health-check.sh --quick
}

# Main script logic
main() {
    print_header
    
    # Parse command line arguments
    case "${1:-}" in
        --development|-d)
            check_prerequisites
            setup_development
            ;;
        --production|-p)
            check_prerequisites
            setup_production
            ;;
        --standard|-s)
            check_prerequisites
            setup_standard
            ;;
        --genai|-g)
            check_prerequisites
            setup_genai
            ;;
        --interactive|-i)
            check_prerequisites
            setup_interactive
            ;;
        --validate|-v)
            validate_deployment
            ;;
        --status)
            show_status
            ;;
        --help|-h|help)
            show_usage
            ;;
        "")
            print_info "No option specified. Use --help for usage information."
            show_usage
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
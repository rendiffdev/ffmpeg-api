#!/bin/bash

# Docker Setup Entrypoint Script
# This script runs the interactive setup within a Docker container

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}"
    echo "========================================"
    echo "   FFmpeg API - Docker Setup Wizard"
    echo "========================================"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check if we're running in interactive mode
check_interactive() {
    if [ ! -t 0 ]; then
        print_error "This setup requires interactive input. Please run with -it flags:"
        echo "docker-compose -f docker-compose.setup.yml run --rm setup"
        exit 1
    fi
}

# Wait for user confirmation
wait_for_confirmation() {
    echo ""
    echo "This setup will:"
    echo "• Generate secure database credentials"
    echo "• Create admin API keys"
    echo "• Configure storage backends"
    echo "• Set up monitoring credentials"
    echo "• Create a complete .env configuration file"
    echo ""
    echo "Any existing .env file will be backed up."
    echo ""
    
    while true; do
        echo -ne "Do you want to continue? [y/N]: "
        read -r response
        case $response in
            [Yy]|[Yy][Ee][Ss])
                break
                ;;
            [Nn]|[Nn][Oo]|"")
                echo "Setup cancelled."
                exit 0
                ;;
            *)
                print_error "Please answer yes or no."
                ;;
        esac
    done
}

# Check for existing configuration
check_existing_config() {
    if [ -f "/host/.env" ]; then
        print_warning "Existing .env configuration found"
        echo ""
        echo "Options:"
        echo "1) Continue and backup existing configuration"
        echo "2) Cancel setup"
        echo ""
        
        while true; do
            echo -ne "Choose option [1]: "
            read -r choice
            case ${choice:-1} in
                1)
                    break
                    ;;
                2)
                    echo "Setup cancelled."
                    exit 0
                    ;;
                *)
                    print_error "Please choose 1 or 2."
                    ;;
            esac
        done
    fi
}

# Run the interactive setup
run_setup() {
    print_success "Starting interactive setup..."
    echo ""
    
    # Change to the host directory where .env should be created
    cd /host
    
    # Run the interactive setup script
    /app/scripts/interactive-setup.sh
    
    if [ $? -eq 0 ]; then
        print_success "Setup completed successfully!"
        echo ""
        echo "Your FFmpeg API is now configured and ready to deploy."
        echo ""
        echo "To start the services:"
        echo "  docker-compose up -d"
        echo ""
        echo "To start with monitoring:"
        echo "  docker-compose --profile monitoring up -d"
        echo ""
        echo "To start with GPU support:"
        echo "  docker-compose --profile gpu up -d"
        echo ""
    else
        print_error "Setup failed. Please check the error messages above."
        exit 1
    fi
}

# Validate the generated configuration
validate_config() {
    if [ -f "/host/.env" ]; then
        print_success "Configuration file created: .env"
        
        # Check for required variables
        local required_vars=("API_HOST" "API_PORT" "DATABASE_TYPE")
        local missing_vars=()
        
        for var in "${required_vars[@]}"; do
            if ! grep -q "^${var}=" /host/.env; then
                missing_vars+=("$var")
            fi
        done
        
        if [ ${#missing_vars[@]} -eq 0 ]; then
            print_success "Configuration validation passed"
        else
            print_error "Missing required variables: ${missing_vars[*]}"
            return 1
        fi
    else
        print_error "Configuration file was not created"
        return 1
    fi
}

# Create necessary directories
create_directories() {
    print_success "Creating necessary directories..."
    
    # Ensure required directories exist on the host
    mkdir -p /host/data
    mkdir -p /host/logs
    mkdir -p /host/storage
    mkdir -p /host/config
    
    # Set appropriate permissions
    chmod 755 /host/data /host/logs /host/storage /host/config
    
    print_success "Directories created successfully"
}

# Copy default configuration files if they don't exist
copy_default_configs() {
    print_success "Setting up default configuration files..."
    
    # Copy storage configuration template
    if [ ! -f "/host/config/storage.yml" ] && [ -f "/app/config/storage.yml.example" ]; then
        cp /app/config/storage.yml.example /host/config/storage.yml
        print_success "Created default storage configuration"
    fi
    
    # Copy other default configs as needed
    # Add more default configurations here
}

# Generate additional security files
generate_security_files() {
    print_success "Generating additional security configurations..."
    
    # Create .env.example for future reference
    if [ -f "/host/.env" ]; then
        # Create a sanitized version without sensitive data
        sed 's/=.*/=your_value_here/g' /host/.env > /host/.env.example.generated
        print_success "Created .env.example.generated for reference"
    fi
}

# Main function
main() {
    print_header
    
    # Pre-setup checks
    check_interactive
    check_existing_config
    wait_for_confirmation
    
    # Setup process
    create_directories
    copy_default_configs
    run_setup
    
    # Post-setup validation and configuration
    if validate_config; then
        generate_security_files
        echo ""
        print_success "=== SETUP COMPLETED SUCCESSFULLY ==="
        echo ""
        echo "Next steps:"
        echo "1. Review the generated .env file"
        echo "2. Customize any additional settings if needed"
        echo "3. Start your FFmpeg API services"
        echo ""
        echo "For help and documentation, see:"
        echo "• DEPLOYMENT.md - Deployment guide"
        echo "• SECURITY.md - Security configuration"
        echo "• README.md - General information"
        echo ""
    else
        print_error "Setup validation failed. Please run setup again."
        exit 1
    fi
}

# Run main function
main "$@"
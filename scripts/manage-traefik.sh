#!/bin/bash

# Traefik SSL/TLS Management Script for FFmpeg API
# Supports automatic SSL certificate management with Let's Encrypt via Traefik

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
TRAEFIK_DIR="./traefik"
TRAEFIK_DATA_DIR="./traefik-data"
ACME_FILE="$TRAEFIK_DATA_DIR/acme.json"
ACME_STAGING_FILE="$TRAEFIK_DATA_DIR/acme-staging.json"

# Utility functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}     Traefik SSL Management${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
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

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# Function to validate FQDN
validate_fqdn() {
    local fqdn="$1"
    
    # Basic FQDN validation
    if [[ ! "$fqdn" =~ ^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$ ]]; then
        return 1
    fi
    
    # Must contain at least one dot
    if [[ ! "$fqdn" == *.* ]]; then
        return 1
    fi
    
    return 0
}

# Function to check if domain is publicly resolvable
check_domain_resolution() {
    local domain="$1"
    local public_ip=""
    
    print_info "Checking domain resolution for $domain..."
    
    # Get the public IP of this server
    public_ip=$(curl -s https://ipv4.icanhazip.com 2>/dev/null || curl -s https://api.ipify.org 2>/dev/null || echo "")
    
    if [ -z "$public_ip" ]; then
        print_warning "Cannot determine public IP address"
        return 1
    fi
    
    # Check if domain resolves to this server
    local resolved_ip=$(nslookup "$domain" 2>/dev/null | grep -A 1 "Name:" | tail -n 1 | awk '{print $2}' || echo "")
    
    if [ "$resolved_ip" = "$public_ip" ]; then
        print_success "Domain $domain resolves to this server ($public_ip)"
        return 0
    else
        print_warning "Domain $domain does not resolve to this server"
        print_info "Domain resolves to: ${resolved_ip:-'unknown'}"
        print_info "Server public IP: $public_ip"
        return 1
    fi
}

# Function to setup Traefik directories and permissions
setup_traefik_directories() {
    print_info "Setting up Traefik directories..."
    
    mkdir -p "$TRAEFIK_DIR"
    mkdir -p "$TRAEFIK_DATA_DIR"
    
    # Create acme.json files with correct permissions
    touch "$ACME_FILE"
    touch "$ACME_STAGING_FILE"
    chmod 600 "$ACME_FILE"
    chmod 600 "$ACME_STAGING_FILE"
    
    print_success "Traefik directories created with proper permissions"
}

# Function to configure Traefik for SSL
configure_traefik_ssl() {
    local domain="$1"
    local email="$2"
    local staging="$3"
    
    print_info "Configuring Traefik for SSL with domain: $domain"
    
    # Update .env file with SSL configuration
    local env_file=".env"
    
    # Create or update environment variables
    if [ -f "$env_file" ]; then
        # Update existing variables
        sed -i.bak "s/^DOMAIN_NAME=.*/DOMAIN_NAME=$domain/" "$env_file" || echo "DOMAIN_NAME=$domain" >> "$env_file"
        sed -i.bak "s/^CERTBOT_EMAIL=.*/CERTBOT_EMAIL=$email/" "$env_file" || echo "CERTBOT_EMAIL=$email" >> "$env_file"
        sed -i.bak "s/^LETSENCRYPT_STAGING=.*/LETSENCRYPT_STAGING=$staging/" "$env_file" || echo "LETSENCRYPT_STAGING=$staging" >> "$env_file"
        sed -i.bak "s/^SSL_ENABLED=.*/SSL_ENABLED=true/" "$env_file" || echo "SSL_ENABLED=true" >> "$env_file"
        sed -i.bak "s/^SSL_TYPE=.*/SSL_TYPE=letsencrypt/" "$env_file" || echo "SSL_TYPE=letsencrypt" >> "$env_file"
        
        if [ "$staging" = "true" ]; then
            sed -i.bak "s/^CERT_RESOLVER=.*/CERT_RESOLVER=letsencrypt-staging/" "$env_file" || echo "CERT_RESOLVER=letsencrypt-staging" >> "$env_file"
        else
            sed -i.bak "s/^CERT_RESOLVER=.*/CERT_RESOLVER=letsencrypt/" "$env_file" || echo "CERT_RESOLVER=letsencrypt" >> "$env_file"
        fi
    else
        # Create new .env file
        cat > "$env_file" << EOF
# SSL/TLS Configuration for Traefik
DOMAIN_NAME=$domain
CERTBOT_EMAIL=$email
LETSENCRYPT_STAGING=$staging
SSL_ENABLED=true
SSL_TYPE=letsencrypt
CERT_RESOLVER=$(if [ "$staging" = "true" ]; then echo "letsencrypt-staging"; else echo "letsencrypt"; fi)
EOF
    fi
    
    print_success "Traefik SSL configuration updated"
}

# Function to start Traefik with SSL
start_traefik_ssl() {
    local domain="$1"
    local email="$2"
    local staging="${3:-false}"
    
    print_info "Starting Traefik with SSL configuration..."
    
    # Check if domain is provided
    if [ -z "$domain" ]; then
        print_error "Domain name is required"
        return 1
    fi
    
    # Validate domain
    if ! validate_fqdn "$domain"; then
        print_error "Invalid domain name: $domain"
        return 1
    fi
    
    # Check domain resolution for production
    if [ "$staging" != "true" ]; then
        if ! check_domain_resolution "$domain"; then
            echo ""
            print_warning "Domain resolution issues detected."
            echo "Options:"
            echo "1. Use staging environment: $0 start $domain $email --staging"
            echo "2. Continue anyway (may fail)"
            echo "3. Fix DNS and try again"
            echo ""
            echo -ne "Continue with production Let's Encrypt? [y/N]: "
            read -r confirm
            if [[ ! $confirm =~ ^[Yy] ]]; then
                print_info "Operation cancelled"
                return 0
            fi
        fi
    fi
    
    # Setup directories
    setup_traefik_directories
    
    # Configure Traefik
    configure_traefik_ssl "$domain" "$email" "$staging"
    
    # Start services
    print_info "Starting Traefik and services..."
    
    if docker-compose -f docker-compose.prod.yml --profile traefik up -d traefik; then
        print_success "Traefik started successfully"
        
        # Wait a moment for Traefik to initialize
        sleep 5
        
        # Start other services
        if docker-compose -f docker-compose.prod.yml --profile traefik up -d; then
            print_success "All services started successfully"
            
            # Display access information
            echo ""
            print_info "Services are now available at:"
            echo "  - API: https://$domain/api/v1/"
            echo "  - Docs: https://$domain/docs"
            echo "  - Health: https://$domain/health"
            echo "  - Traefik Dashboard: https://traefik.$domain/"
            if grep -q "ENABLE_MONITORING=true" .env 2>/dev/null; then
                echo "  - Grafana: https://grafana.$domain/"
                echo "  - Prometheus: https://prometheus.$domain/"
            fi
            
        else
            print_error "Failed to start some services"
            return 1
        fi
    else
        print_error "Failed to start Traefik"
        return 1
    fi
}

# Function to check SSL status
check_ssl_status() {
    local domain="${1:-}"
    
    echo -e "${CYAN}SSL Certificate Status${NC}"
    echo ""
    
    # Get domain from environment if not provided
    if [ -z "$domain" ]; then
        if [ -f ".env" ]; then
            domain=$(grep "^DOMAIN_NAME=" .env 2>/dev/null | cut -d= -f2)
        fi
    fi
    
    if [ -z "$domain" ]; then
        print_error "No domain specified and no DOMAIN_NAME found in .env"
        return 1
    fi
    
    print_info "Checking SSL status for: $domain"
    echo ""
    
    # Check if Traefik is running
    if ! docker-compose ps traefik | grep -q "Up"; then
        print_error "Traefik is not running"
        echo "Start Traefik with: $0 start $domain email@example.com"
        return 1
    fi
    
    print_success "Traefik is running"
    
    # Check ACME certificate files
    local cert_resolver
    if [ -f ".env" ]; then
        cert_resolver=$(grep "^CERT_RESOLVER=" .env 2>/dev/null | cut -d= -f2)
    fi
    
    local acme_file="$ACME_FILE"
    if [ "$cert_resolver" = "letsencrypt-staging" ]; then
        acme_file="$ACME_STAGING_FILE"
    fi
    
    if [ -f "$acme_file" ] && [ -s "$acme_file" ]; then
        print_success "ACME certificate file exists"
        
        # Check if certificate exists for domain
        if jq -e ".letsencrypt.Certificates[] | select(.domain.main == \"$domain\")" "$acme_file" >/dev/null 2>&1; then
            print_success "Certificate found for domain: $domain"
            
            # Get certificate info
            local cert_info
            cert_info=$(jq -r ".letsencrypt.Certificates[] | select(.domain.main == \"$domain\") | .domain.main + \" (\" + (.domain.sans // [] | join(\", \")) + \")\"" "$acme_file" 2>/dev/null)
            print_info "Certificate covers: $cert_info"
        else
            print_warning "No certificate found for domain: $domain"
        fi
    else
        print_warning "ACME certificate file is empty or missing"
        print_info "Certificates will be generated automatically when accessing HTTPS endpoints"
    fi
    
    # Test HTTPS connectivity
    echo ""
    print_info "Testing HTTPS connectivity..."
    
    local endpoints=("/health" "/api/v1/health")
    local success=false
    
    for endpoint in "${endpoints[@]}"; do
        if curl -s -k --connect-timeout 10 "https://$domain$endpoint" >/dev/null 2>&1; then
            print_success "HTTPS endpoint accessible: $endpoint"
            success=true
            break
        fi
    done
    
    if [ "$success" = "false" ]; then
        print_warning "HTTPS endpoints not accessible"
        print_info "This may be normal if services are still starting"
    fi
    
    # Test Traefik dashboard
    if curl -s -k --connect-timeout 10 "https://traefik.$domain/api/rawdata" >/dev/null 2>&1; then
        print_success "Traefik dashboard is accessible"
    else
        print_warning "Traefik dashboard not accessible"
    fi
}

# Function to view Traefik logs
view_logs() {
    local service="${1:-traefik}"
    
    print_info "Viewing logs for: $service"
    echo ""
    
    case $service in
        traefik)
            docker-compose logs -f traefik
            ;;
        access)
            if [ -f "./traefik-logs/access.log" ]; then
                tail -f ./traefik-logs/access.log
            else
                print_error "Access log not found"
            fi
            ;;
        all)
            docker-compose -f docker-compose.prod.yml --profile traefik logs -f
            ;;
        *)
            docker-compose logs -f "$service"
            ;;
    esac
}

# Function to restart Traefik
restart_traefik() {
    print_info "Restarting Traefik..."
    
    if docker-compose -f docker-compose.prod.yml --profile traefik restart traefik; then
        print_success "Traefik restarted successfully"
    else
        print_error "Failed to restart Traefik"
        return 1
    fi
}

# Function to stop Traefik and services
stop_traefik() {
    print_info "Stopping Traefik and services..."
    
    if docker-compose -f docker-compose.prod.yml --profile traefik down; then
        print_success "Services stopped successfully"
    else
        print_error "Failed to stop services"
        return 1
    fi
}

# Function to validate Traefik configuration
validate_config() {
    local domain="${1:-localhost}"
    
    echo -e "${CYAN}Traefik Configuration Validation${NC}"
    echo ""
    
    local valid=true
    
    # Check configuration files
    print_info "1. Checking configuration files..."
    
    if [ -f "$TRAEFIK_DIR/traefik.yml" ]; then
        print_success "Traefik static configuration exists"
    else
        print_error "Traefik static configuration missing"
        valid=false
    fi
    
    if [ -f "$TRAEFIK_DIR/dynamic.yml" ]; then
        print_success "Traefik dynamic configuration exists"
    else
        print_warning "Traefik dynamic configuration missing (optional)"
    fi
    
    # Check environment configuration
    echo ""
    print_info "2. Checking environment configuration..."
    
    if [ -f ".env" ]; then
        print_success ".env file exists"
        
        local required_vars=("DOMAIN_NAME" "CERTBOT_EMAIL")
        for var in "${required_vars[@]}"; do
            if grep -q "^$var=" .env; then
                print_success "$var is configured"
            else
                print_warning "$var is not configured"
            fi
        done
    else
        print_warning ".env file not found"
    fi
    
    # Check Docker Compose configuration
    echo ""
    print_info "3. Checking Docker Compose configuration..."
    
    if docker-compose -f docker-compose.prod.yml --profile traefik config >/dev/null 2>&1; then
        print_success "Docker Compose configuration is valid"
    else
        print_error "Docker Compose configuration has errors"
        valid=false
    fi
    
    # Check ACME file permissions
    echo ""
    print_info "4. Checking ACME file permissions..."
    
    for acme_file in "$ACME_FILE" "$ACME_STAGING_FILE"; do
        if [ -f "$acme_file" ]; then
            local perms=$(stat -c "%a" "$acme_file" 2>/dev/null || stat -f "%A" "$acme_file" 2>/dev/null)
            if [ "$perms" = "600" ]; then
                print_success "$(basename "$acme_file") has correct permissions (600)"
            else
                print_warning "$(basename "$acme_file") has incorrect permissions ($perms), should be 600"
                chmod 600 "$acme_file"
                print_success "Fixed permissions for $(basename "$acme_file")"
            fi
        fi
    done
    
    # Check domain resolution
    echo ""
    print_info "5. Checking domain resolution..."
    
    if [ "$domain" != "localhost" ]; then
        if check_domain_resolution "$domain"; then
            print_success "Domain resolution is correct"
        else
            print_warning "Domain resolution issues detected"
        fi
    else
        print_info "Skipping domain resolution check for localhost"
    fi
    
    # Summary
    echo ""
    if [ "$valid" = "true" ]; then
        print_success "Traefik configuration validation completed successfully!"
    else
        print_error "Traefik configuration validation found issues"
        return 1
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start <domain> <email> [--staging]    Start Traefik with SSL for domain"
    echo "  status [domain]                       Check SSL certificate status"
    echo "  restart                               Restart Traefik service"
    echo "  stop                                  Stop Traefik and all services"
    echo "  logs [service]                        View logs (traefik|access|all|service-name)"
    echo "  validate [domain]                     Validate Traefik configuration"
    echo "  help                                  Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start api.example.com admin@example.com"
    echo "  $0 start api.example.com admin@example.com --staging"
    echo "  $0 status api.example.com"
    echo "  $0 logs traefik"
    echo "  $0 validate api.example.com"
    echo ""
    echo "Notes:"
    echo "  - Use --staging flag for testing with Let's Encrypt staging environment"
    echo "  - Domain must resolve to this server for production certificates"
    echo "  - Traefik will automatically obtain and renew SSL certificates"
    echo ""
}

# Main function
main() {
    local command="${1:-help}"
    
    case $command in
        start)
            if [ $# -lt 3 ]; then
                print_error "Domain and email required"
                echo "Usage: $0 start <domain> <email> [--staging]"
                exit 1
            fi
            
            local domain="$2"
            local email="$3"
            local staging="false"
            
            # Check for staging flag
            for arg in "$@"; do
                if [ "$arg" = "--staging" ]; then
                    staging="true"
                    break
                fi
            done
            
            print_header
            start_traefik_ssl "$domain" "$email" "$staging"
            ;;
            
        status|list)
            local domain="${2:-}"
            print_header
            check_ssl_status "$domain"
            ;;
            
        restart)
            print_header
            restart_traefik
            ;;
            
        stop)
            print_header
            stop_traefik
            ;;
            
        logs)
            local service="${2:-traefik}"
            view_logs "$service"
            ;;
            
        validate)
            local domain="${2:-localhost}"
            print_header
            validate_config "$domain"
            ;;
            
        help|--help|-h)
            print_header
            show_usage
            ;;
            
        *)
            print_header
            print_error "Unknown command: $command"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Check dependencies
check_dependencies() {
    local missing_deps=()
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        missing_deps+=("docker-compose")
    fi
    
    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    fi
    
    if ! command -v jq &> /dev/null; then
        missing_deps+=("jq")
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        print_error "Missing required dependencies: ${missing_deps[*]}"
        echo "Please install the missing dependencies and try again."
        exit 1
    fi
}

# Check dependencies before running
check_dependencies

# Run main function
main "$@"
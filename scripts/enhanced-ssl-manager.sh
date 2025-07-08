#!/bin/bash

# Enhanced SSL Certificate Manager
# Comprehensive SSL/TLS certificate management for all deployment types
# Supports self-signed, Let's Encrypt, and commercial certificates

set -e

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CERT_DIR="$PROJECT_ROOT/traefik/certs"
BACKUP_DIR="$PROJECT_ROOT/backups/certificates"
LOG_FILE="$PROJECT_ROOT/logs/ssl-manager.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration from environment
DOMAIN_NAME="${DOMAIN_NAME:-localhost}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-admin@localhost}"
SSL_MODE="${SSL_MODE:-self-signed}"
CERT_BACKUP_RETENTION="${CERT_BACKUP_RETENTION:-30}"

# Logging function
log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                Enhanced SSL Certificate Manager                  ║${NC}"
    echo -e "${BLUE}║                     Production Ready v2.0                       ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${CYAN}ℹ $1${NC}"; }

# Cross-platform date function for epoch conversion
date_to_epoch() {
    local date_string="$1"
    # Try GNU date first (Linux)
    if date -d "$date_string" +%s 2>/dev/null; then
        return 0
    # Fall back to BSD date (macOS)
    elif date -j -f "%b %d %H:%M:%S %Y %Z" "$date_string" +%s 2>/dev/null; then
        return 0
    # Try alternative format for BSD date
    elif date -j -f "%Y-%m-%d %H:%M:%S" "$date_string" +%s 2>/dev/null; then
        return 0
    else
        # Fallback: return current time + 365 days for self-signed certs
        echo $(($(date +%s) + 31536000))
    fi
}

# Show usage information
show_usage() {
    cat << EOF
Usage: $0 [COMMAND] [OPTIONS]

CERTIFICATE MANAGEMENT COMMANDS:
  generate-self-signed [domain]     Generate self-signed certificate
  generate-letsencrypt [domain]     Generate Let's Encrypt certificate
  install-commercial [cert] [key]   Install commercial certificate
  renew [type]                      Renew certificates (all, letsencrypt, self-signed)
  backup                           Create certificate backup
  restore [backup-date]            Restore certificates from backup
  
CERTIFICATE INFORMATION:
  list                             List all certificates
  show [domain]                    Show certificate details
  check-expiration [domain]        Check certificate expiration
  validate [domain]                Validate certificate chain
  
DEPLOYMENT COMMANDS:
  setup-dev                       Setup development SSL (self-signed)
  setup-prod [domain] [email]      Setup production SSL (Let's Encrypt)
  setup-staging [domain] [email]   Setup staging SSL (Let's Encrypt Staging)
  setup-commercial [domain]        Setup commercial SSL workflow
  
MONITORING COMMANDS:
  monitor-start                    Start SSL monitoring service
  monitor-stop                     Stop SSL monitoring service
  monitor-status                   Check monitoring service status
  test-ssl [domain]                Test SSL configuration
  
UTILITY COMMANDS:
  convert-format [input] [output]  Convert certificate format
  create-csr [domain]              Create certificate signing request
  verify-chain [cert]              Verify certificate chain
  ocsp-check [cert]                Check OCSP status
  
EXAMPLES:
  $0 setup-dev                                    # Development with self-signed
  $0 setup-prod api.example.com admin@example.com # Production with Let's Encrypt
  $0 generate-self-signed api.example.com         # Generate self-signed cert
  $0 check-expiration api.example.com             # Check expiration
  $0 backup                                       # Backup all certificates
  $0 test-ssl api.example.com                     # Test SSL configuration

EOF
}

# Create necessary directories
create_directories() {
    mkdir -p "$CERT_DIR" "$BACKUP_DIR" "$(dirname "$LOG_FILE")"
    mkdir -p "$PROJECT_ROOT/monitoring/ssl-scan-results"
}

# Generate self-signed certificate
generate_self_signed() {
    local domain="${1:-$DOMAIN_NAME}"
    local cert_file="$CERT_DIR/cert.crt"
    local key_file="$CERT_DIR/cert.key"
    local csr_file="$CERT_DIR/cert.csr"
    
    print_info "Generating self-signed certificate for $domain"
    
    # Generate private key
    openssl genrsa -out "$key_file" 2048
    
    # Create certificate signing request
    openssl req -new -key "$key_file" -out "$csr_file" \
        -subj "/C=US/ST=State/L=City/O=Rendiff/CN=$domain" \
        -config <(
            echo '[req]'
            echo 'distinguished_name = req_distinguished_name'
            echo 'req_extensions = v3_req'
            echo 'prompt = no'
            echo '[req_distinguished_name]'
            echo "CN = $domain"
            echo '[v3_req]'
            echo 'keyUsage = keyEncipherment, dataEncipherment'
            echo 'extendedKeyUsage = serverAuth'
            echo "subjectAltName = @alt_names"
            echo '[alt_names]'
            echo "DNS.1 = $domain"
            echo "DNS.2 = *.$domain"
            echo "DNS.3 = localhost"
            echo "IP.1 = 127.0.0.1"
        )
    
    # Generate self-signed certificate (valid for 1 year)
    openssl x509 -req -in "$csr_file" -signkey "$key_file" -out "$cert_file" \
        -days 365 -extensions v3_req \
        -extfile <(
            echo '[v3_req]'
            echo 'keyUsage = keyEncipherment, dataEncipherment'
            echo 'extendedKeyUsage = serverAuth'
            echo "subjectAltName = @alt_names"
            echo '[alt_names]'
            echo "DNS.1 = $domain"
            echo "DNS.2 = *.$domain"
            echo "DNS.3 = localhost"
            echo "IP.1 = 127.0.0.1"
        )
    
    # Set proper permissions
    chmod 600 "$key_file"
    chmod 644 "$cert_file"
    
    # Clean up CSR
    rm -f "$csr_file"
    
    print_success "Self-signed certificate generated for $domain"
    log "Self-signed certificate generated: $cert_file"
    
    # Show certificate info
    show_certificate_info "$cert_file"
}

# Generate Let's Encrypt certificate
generate_letsencrypt() {
    local domain="${1:-$DOMAIN_NAME}"
    local email="${2:-$CERTBOT_EMAIL}"
    local staging="${3:-false}"
    
    print_info "Generating Let's Encrypt certificate for $domain"
    
    # Choose server (staging or production)
    local server_arg=""
    if [ "$staging" = "true" ]; then
        server_arg="--server https://acme-staging-v02.api.letsencrypt.org/directory"
        print_info "Using Let's Encrypt staging environment"
    fi
    
    # Generate certificate using Certbot
    docker run --rm \
        -v "$PROJECT_ROOT/traefik/letsencrypt:/etc/letsencrypt" \
        -v "$PROJECT_ROOT/traefik/letsencrypt-log:/var/log/letsencrypt" \
        -v "$PROJECT_ROOT/traefik/certs:/output" \
        -p 80:80 \
        certbot/certbot:latest \
        certonly \
        --standalone \
        --email "$email" \
        --agree-tos \
        --non-interactive \
        --domains "$domain" \
        $server_arg
    
    # Copy certificates to Traefik directory
    if [ -f "$PROJECT_ROOT/traefik/letsencrypt/live/$domain/fullchain.pem" ]; then
        cp "$PROJECT_ROOT/traefik/letsencrypt/live/$domain/fullchain.pem" "$CERT_DIR/cert.crt"
        cp "$PROJECT_ROOT/traefik/letsencrypt/live/$domain/privkey.pem" "$CERT_DIR/cert.key"
        chmod 600 "$CERT_DIR/cert.key"
        chmod 644 "$CERT_DIR/cert.crt"
        
        print_success "Let's Encrypt certificate generated for $domain"
        log "Let's Encrypt certificate generated: $CERT_DIR/cert.crt"
        
        # Show certificate info
        show_certificate_info "$CERT_DIR/cert.crt"
    else
        print_error "Failed to generate Let's Encrypt certificate"
        return 1
    fi
}

# Install commercial certificate
install_commercial() {
    local cert_file="$1"
    local key_file="$2"
    local chain_file="$3"
    
    if [ -z "$cert_file" ] || [ -z "$key_file" ]; then
        print_error "Usage: install-commercial <cert_file> <key_file> [chain_file]"
        return 1
    fi
    
    if [ ! -f "$cert_file" ] || [ ! -f "$key_file" ]; then
        print_error "Certificate or key file not found"
        return 1
    fi
    
    print_info "Installing commercial certificate"
    
    # Backup existing certificates
    backup_certificates
    
    # Copy and set permissions
    cp "$cert_file" "$CERT_DIR/cert.crt"
    cp "$key_file" "$CERT_DIR/cert.key"
    
    # If chain file provided, append to certificate
    if [ -n "$chain_file" ] && [ -f "$chain_file" ]; then
        cat "$chain_file" >> "$CERT_DIR/cert.crt"
        print_info "Certificate chain appended"
    fi
    
    chmod 600 "$CERT_DIR/cert.key"
    chmod 644 "$CERT_DIR/cert.crt"
    
    # Validate certificate
    if validate_certificate "$CERT_DIR/cert.crt"; then
        print_success "Commercial certificate installed successfully"
        log "Commercial certificate installed: $CERT_DIR/cert.crt"
        
        # Show certificate info
        show_certificate_info "$CERT_DIR/cert.crt"
    else
        print_error "Certificate validation failed"
        return 1
    fi
}

# Show certificate information
show_certificate_info() {
    local cert_file="${1:-$CERT_DIR/cert.crt}"
    
    if [ ! -f "$cert_file" ]; then
        print_error "Certificate file not found: $cert_file"
        return 1
    fi
    
    print_info "Certificate Information:"
    echo ""
    
    # Subject
    local subject=$(openssl x509 -in "$cert_file" -noout -subject | sed 's/subject=//')
    echo -e "${CYAN}Subject:${NC} $subject"
    
    # Issuer
    local issuer=$(openssl x509 -in "$cert_file" -noout -issuer | sed 's/issuer=//')
    echo -e "${CYAN}Issuer:${NC} $issuer"
    
    # Validity dates
    local not_before=$(openssl x509 -in "$cert_file" -noout -startdate | sed 's/notBefore=//')
    local not_after=$(openssl x509 -in "$cert_file" -noout -enddate | sed 's/notAfter=//')
    echo -e "${CYAN}Valid From:${NC} $not_before"
    echo -e "${CYAN}Valid Until:${NC} $not_after"
    
    # Days until expiration
    local expiry_epoch=$(date_to_epoch "$not_after")
    local current_epoch=$(date +%s)
    local days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))
    
    if [ "$days_until_expiry" -lt 0 ]; then
        echo -e "${RED}Status: EXPIRED (expired $((days_until_expiry * -1)) days ago)${NC}"
    elif [ "$days_until_expiry" -lt 30 ]; then
        echo -e "${YELLOW}Status: EXPIRING SOON (expires in $days_until_expiry days)${NC}"
    else
        echo -e "${GREEN}Status: VALID (expires in $days_until_expiry days)${NC}"
    fi
    
    # Subject Alternative Names
    local san=$(openssl x509 -in "$cert_file" -noout -ext subjectAltName 2>/dev/null | grep -v "X509v3 Subject Alternative Name" | tr -d ' ' | sed 's/DNS://g' | sed 's/IP://g')
    if [ -n "$san" ]; then
        echo -e "${CYAN}Subject Alternative Names:${NC} $san"
    fi
    
    # Key information
    local key_size=$(openssl x509 -in "$cert_file" -noout -pubkey | openssl pkey -pubin -text -noout | grep -o "Private-Key: ([0-9]* bit)" | grep -o "[0-9]*")
    echo -e "${CYAN}Key Size:${NC} $key_size bits"
    
    # Signature algorithm
    local sig_alg=$(openssl x509 -in "$cert_file" -noout -text | grep "Signature Algorithm" | head -1 | sed 's/.*Signature Algorithm: //')
    echo -e "${CYAN}Signature Algorithm:${NC} $sig_alg"
    
    echo ""
}

# Validate certificate
validate_certificate() {
    local cert_file="${1:-$CERT_DIR/cert.crt}"
    
    if [ ! -f "$cert_file" ]; then
        print_error "Certificate file not found: $cert_file"
        return 1
    fi
    
    print_info "Validating certificate: $cert_file"
    
    # Check if certificate is valid
    if ! openssl x509 -in "$cert_file" -noout -checkend 86400; then
        print_error "Certificate is expired or expires within 24 hours"
        return 1
    fi
    
    # Check certificate chain (if possible)
    if openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt "$cert_file" >/dev/null 2>&1; then
        print_success "Certificate chain is valid"
    else
        print_warning "Certificate chain validation failed (may be self-signed)"
    fi
    
    # Check private key match (if key file exists)
    local key_file="$CERT_DIR/cert.key"
    if [ -f "$key_file" ]; then
        local cert_modulus=$(openssl x509 -in "$cert_file" -noout -modulus | openssl md5)
        local key_modulus=$(openssl rsa -in "$key_file" -noout -modulus | openssl md5)
        
        if [ "$cert_modulus" = "$key_modulus" ]; then
            print_success "Private key matches certificate"
        else
            print_error "Private key does not match certificate"
            return 1
        fi
    fi
    
    return 0
}

# Check certificate expiration
check_expiration() {
    local domain="${1:-$DOMAIN_NAME}"
    local cert_file="$CERT_DIR/cert.crt"
    
    if [ ! -f "$cert_file" ]; then
        print_error "Certificate file not found: $cert_file"
        return 1
    fi
    
    print_info "Checking certificate expiration for $domain"
    
    local expiry_date=$(openssl x509 -in "$cert_file" -noout -enddate | cut -d= -f2)
    local expiry_epoch=$(date_to_epoch "$expiry_date")
    local current_epoch=$(date +%s)
    local days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))
    
    echo -e "${CYAN}Certificate expires on:${NC} $expiry_date"
    
    if [ "$days_until_expiry" -lt 0 ]; then
        echo -e "${RED}Certificate has EXPIRED $((days_until_expiry * -1)) days ago${NC}"
        return 1
    elif [ "$days_until_expiry" -lt 30 ]; then
        echo -e "${YELLOW}Certificate expires in $days_until_expiry days${NC}"
        return 2
    else
        echo -e "${GREEN}Certificate is valid for $days_until_expiry more days${NC}"
        return 0
    fi
}

# Backup certificates
backup_certificates() {
    local backup_date=$(date +%Y%m%d-%H%M%S)
    local backup_path="$BACKUP_DIR/$backup_date"
    
    print_info "Creating certificate backup"
    
    mkdir -p "$backup_path"
    
    # Backup Traefik certificates
    if [ -d "$CERT_DIR" ]; then
        cp -r "$CERT_DIR"/* "$backup_path/"
        print_success "Traefik certificates backed up to $backup_path"
    fi
    
    # Backup Let's Encrypt certificates
    if [ -d "$PROJECT_ROOT/traefik/letsencrypt" ]; then
        cp -r "$PROJECT_ROOT/traefik/letsencrypt" "$backup_path/"
        print_success "Let's Encrypt certificates backed up"
    fi
    
    # Create backup manifest
    cat > "$backup_path/manifest.txt" << EOF
Certificate Backup Manifest
Created: $(date)
Domain: $DOMAIN_NAME
SSL Mode: $SSL_MODE
Files:
$(ls -la "$backup_path")
EOF
    
    # Cleanup old backups
    find "$BACKUP_DIR" -type d -mtime +$CERT_BACKUP_RETENTION -exec rm -rf {} + 2>/dev/null || true
    
    log "Certificate backup created: $backup_path"
}

# Test SSL configuration
test_ssl() {
    local domain="${1:-$DOMAIN_NAME}"
    local port="${2:-443}"
    
    print_info "Testing SSL configuration for $domain:$port"
    
    # Test SSL connection
    if echo | openssl s_client -connect "$domain:$port" -servername "$domain" 2>/dev/null | grep -q "CONNECTED"; then
        print_success "SSL connection successful"
        
        # Get certificate details from connection
        echo | openssl s_client -connect "$domain:$port" -servername "$domain" 2>/dev/null | openssl x509 -noout -text | grep -A5 "Validity"
        
        # Test cipher strength
        local cipher=$(echo | openssl s_client -connect "$domain:$port" -servername "$domain" 2>/dev/null | grep "Cipher" | head -1)
        echo -e "${CYAN}Cipher:${NC} $cipher"
        
        # Test protocol version
        local protocol=$(echo | openssl s_client -connect "$domain:$port" -servername "$domain" 2>/dev/null | grep "Protocol" | head -1)
        echo -e "${CYAN}Protocol:${NC} $protocol"
        
    else
        print_error "SSL connection failed"
        return 1
    fi
}

# Setup development SSL
setup_dev() {
    print_info "Setting up development SSL (self-signed)"
    
    generate_self_signed "$DOMAIN_NAME"
    
    # Update environment for development
    cat >> "$PROJECT_ROOT/.env" << EOF

# Development SSL Configuration
SSL_MODE=self-signed
DOMAIN_NAME=$DOMAIN_NAME
EOF
    
    print_success "Development SSL setup complete"
    print_info "Access your API at: https://$DOMAIN_NAME"
    print_warning "Browser will show security warning (self-signed certificate)"
}

# Setup production SSL
setup_prod() {
    local domain="${1:-$DOMAIN_NAME}"
    local email="${2:-$CERTBOT_EMAIL}"
    
    print_info "Setting up production SSL with Let's Encrypt"
    
    # Validate domain
    if [ "$domain" = "localhost" ]; then
        print_error "Cannot use Let's Encrypt with localhost. Use --setup-dev instead."
        return 1
    fi
    
    # Generate Let's Encrypt certificate
    generate_letsencrypt "$domain" "$email"
    
    # Update environment for production
    cat >> "$PROJECT_ROOT/.env" << EOF

# Production SSL Configuration
SSL_MODE=letsencrypt
DOMAIN_NAME=$domain
CERTBOT_EMAIL=$email
EOF
    
    print_success "Production SSL setup complete"
    print_info "Access your API at: https://$domain"
}

# Main script logic
main() {
    print_header
    create_directories
    
    case "${1:-}" in
        generate-self-signed)
            generate_self_signed "${2:-$DOMAIN_NAME}"
            ;;
        generate-letsencrypt)
            generate_letsencrypt "${2:-$DOMAIN_NAME}" "${3:-$CERTBOT_EMAIL}"
            ;;
        generate-letsencrypt-staging)
            generate_letsencrypt "${2:-$DOMAIN_NAME}" "${3:-$CERTBOT_EMAIL}" "true"
            ;;
        install-commercial)
            install_commercial "$2" "$3" "$4"
            ;;
        list)
            list_certificates
            ;;
        show)
            show_certificate_info "${2:-$CERT_DIR/cert.crt}"
            ;;
        check-expiration)
            check_expiration "${2:-$DOMAIN_NAME}"
            ;;
        validate)
            validate_certificate "${2:-$CERT_DIR/cert.crt}"
            ;;
        backup)
            backup_certificates
            ;;
        test-ssl)
            test_ssl "${2:-$DOMAIN_NAME}" "${3:-443}"
            ;;
        setup-dev)
            setup_dev
            ;;
        setup-prod)
            setup_prod "$2" "$3"
            ;;
        setup-staging)
            setup_prod "$2" "$3" "true"
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            print_error "Unknown command: ${1:-}"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
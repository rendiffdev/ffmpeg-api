#!/bin/bash

# SSL Certificate Management Script for FFmpeg API
# Supports self-signed certificates and Let's Encrypt

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
SSL_DIR="./ssl"
NGINX_SSL_DIR="./nginx/ssl"
CERT_VALIDITY_DAYS=365
LETSENCRYPT_DIR="./letsencrypt"

# Utility functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}     SSL Certificate Management${NC}"
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

# Function to create directories
create_ssl_directories() {
    mkdir -p "$SSL_DIR"
    mkdir -p "$NGINX_SSL_DIR"
    mkdir -p "$LETSENCRYPT_DIR"
    
    print_success "SSL directories created"
}

# Function to generate self-signed certificate
generate_self_signed() {
    local domain="$1"
    local cert_file="$NGINX_SSL_DIR/cert.pem"
    local key_file="$NGINX_SSL_DIR/key.pem"
    
    print_info "Generating self-signed certificate for $domain..."
    
    # Create OpenSSL configuration
    local ssl_config="$SSL_DIR/openssl.cnf"
    cat > "$ssl_config" << EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C=US
ST=State
L=City
O=Organization
OU=IT Department
CN=$domain

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = $domain
DNS.2 = *.$domain
DNS.3 = localhost
IP.1 = 127.0.0.1
EOF

    # Generate private key
    openssl genrsa -out "$key_file" 2048
    
    # Generate certificate
    openssl req -new -x509 -key "$key_file" -out "$cert_file" \
        -days $CERT_VALIDITY_DAYS -config "$ssl_config" -extensions v3_req
    
    # Set proper permissions
    chmod 600 "$key_file"
    chmod 644 "$cert_file"
    
    print_success "Self-signed certificate generated"
    print_info "Certificate: $cert_file"
    print_info "Private key: $key_file"
    print_info "Valid for: $CERT_VALIDITY_DAYS days"
    
    # Save certificate info
    save_cert_info "self-signed" "$domain" "$cert_file" "$key_file"
}

# Function to generate Let's Encrypt certificate
generate_letsencrypt() {
    local domain="$1"
    local email="$2"
    local staging="$3"
    
    print_info "Setting up Let's Encrypt certificate for $domain..."
    
    # Check if certbot is available
    if ! command -v certbot &> /dev/null; then
        print_error "Certbot is not installed. Installing..."
        install_certbot
    fi
    
    # Prepare certbot options
    local certbot_opts="--nginx --agree-tos --non-interactive"
    
    if [ "$staging" = "true" ]; then
        certbot_opts="$certbot_opts --staging"
        print_info "Using Let's Encrypt staging environment"
    fi
    
    if [ -n "$email" ]; then
        certbot_opts="$certbot_opts --email $email"
    else
        certbot_opts="$certbot_opts --register-unsafely-without-email"
    fi
    
    # Create temporary nginx configuration for domain validation
    create_temp_nginx_config "$domain"
    
    # Start nginx for domain validation
    docker-compose up -d nginx
    
    # Wait for nginx to be ready
    sleep 5
    
    # Run certbot
    if certbot $certbot_opts --domains "$domain"; then
        print_success "Let's Encrypt certificate obtained successfully"
        
        # Copy certificates to our SSL directory
        local cert_source="/etc/letsencrypt/live/$domain"
        cp "$cert_source/fullchain.pem" "$NGINX_SSL_DIR/cert.pem"
        cp "$cert_source/privkey.pem" "$NGINX_SSL_DIR/key.pem"
        
        # Set proper permissions
        chmod 600 "$NGINX_SSL_DIR/key.pem"
        chmod 644 "$NGINX_SSL_DIR/cert.pem"
        
        # Save certificate info
        save_cert_info "letsencrypt" "$domain" "$NGINX_SSL_DIR/cert.pem" "$NGINX_SSL_DIR/key.pem"
        
        # Set up auto-renewal
        setup_cert_renewal "$domain"
        
    else
        print_error "Failed to obtain Let's Encrypt certificate"
        print_info "Falling back to self-signed certificate..."
        generate_self_signed "$domain"
    fi
    
    # Clean up temporary nginx config
    cleanup_temp_nginx_config
}

# Function to install certbot
install_certbot() {
    print_info "Installing Certbot..."
    
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y certbot python3-certbot-nginx
    elif command -v yum &> /dev/null; then
        sudo yum install -y certbot python3-certbot-nginx
    elif command -v brew &> /dev/null; then
        brew install certbot
    else
        print_error "Cannot install Certbot automatically. Please install manually."
        exit 1
    fi
    
    print_success "Certbot installed"
}

# Function to create temporary nginx config for Let's Encrypt validation
create_temp_nginx_config() {
    local domain="$1"
    local temp_config="./nginx/nginx-temp.conf"
    
    cat > "$temp_config" << EOF
events {
    worker_connections 1024;
}

http {
    server {
        listen 80;
        server_name $domain;
        
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }
        
        location / {
            return 301 https://\$server_name\$request_uri;
        }
    }
}
EOF
    
    print_info "Temporary nginx configuration created"
}

# Function to cleanup temporary nginx config
cleanup_temp_nginx_config() {
    local temp_config="./nginx/nginx-temp.conf"
    if [ -f "$temp_config" ]; then
        rm "$temp_config"
    fi
}

# Function to save certificate information
save_cert_info() {
    local cert_type="$1"
    local domain="$2"
    local cert_file="$3"
    local key_file="$4"
    
    local info_file="$SSL_DIR/cert_info.json"
    
    cat > "$info_file" << EOF
{
  "type": "$cert_type",
  "domain": "$domain",
  "certificate": "$cert_file",
  "private_key": "$key_file",
  "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "expires": "$(date -u -d "+${CERT_VALIDITY_DAYS} days" +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
    
    print_success "Certificate information saved to $info_file"
}

# Function to set up certificate auto-renewal
setup_cert_renewal() {
    local domain="$1"
    
    # Create renewal script
    local renewal_script="$SSL_DIR/renew_cert.sh"
    
    cat > "$renewal_script" << EOF
#!/bin/bash
# Auto-renewal script for Let's Encrypt certificates

set -e

echo "Starting certificate renewal check..."

# Check if certificate needs renewal
if certbot renew --dry-run; then
    echo "Certificate renewal check passed"
    
    # Perform actual renewal
    if certbot renew --nginx; then
        echo "Certificate renewed successfully"
        
        # Copy new certificates
        cp /etc/letsencrypt/live/$domain/fullchain.pem $NGINX_SSL_DIR/cert.pem
        cp /etc/letsencrypt/live/$domain/privkey.pem $NGINX_SSL_DIR/key.pem
        
        # Restart nginx
        docker-compose restart nginx
        
        echo "Nginx restarted with new certificates"
    else
        echo "Certificate renewal failed"
        exit 1
    fi
else
    echo "Certificate renewal not needed"
fi
EOF
    
    chmod +x "$renewal_script"
    
    # Add to crontab for automatic renewal
    local cron_job="0 3 * * * $renewal_script >> $SSL_DIR/renewal.log 2>&1"
    
    # Check if cron job already exists
    if ! crontab -l 2>/dev/null | grep -q "$renewal_script"; then
        (crontab -l 2>/dev/null; echo "$cron_job") | crontab -
        print_success "Auto-renewal cron job added"
    fi
    
    print_info "Certificates will be automatically renewed daily at 3 AM"
}

# Function to list certificate information
list_certificates() {
    echo -e "${CYAN}SSL Certificate Status${NC}"
    echo ""
    
    local info_file="$SSL_DIR/cert_info.json"
    
    if [ -f "$info_file" ]; then
        local cert_type=$(jq -r '.type' "$info_file" 2>/dev/null || echo "unknown")
        local domain=$(jq -r '.domain' "$info_file" 2>/dev/null || echo "unknown")
        local created=$(jq -r '.created' "$info_file" 2>/dev/null || echo "unknown")
        local expires=$(jq -r '.expires' "$info_file" 2>/dev/null || echo "unknown")
        
        echo "Certificate Type: $cert_type"
        echo "Domain: $domain"
        echo "Created: $created"
        echo "Expires: $expires"
        echo ""
        
        # Check certificate validity
        if [ -f "$NGINX_SSL_DIR/cert.pem" ]; then
            local cert_info=$(openssl x509 -in "$NGINX_SSL_DIR/cert.pem" -text -noout 2>/dev/null || echo "")
            if [ -n "$cert_info" ]; then
                local subject=$(echo "$cert_info" | grep "Subject:" | sed 's/.*CN=//' | sed 's/,.*//')
                local not_after=$(echo "$cert_info" | grep "Not After" | sed 's/.*: //')
                
                echo "Certificate Subject: $subject"
                echo "Valid Until: $not_after"
                
                # Check if certificate is expiring soon
                local exp_timestamp=$(date -d "$not_after" +%s 2>/dev/null || echo "0")
                local current_timestamp=$(date +%s)
                local days_until_expiry=$(( (exp_timestamp - current_timestamp) / 86400 ))
                
                if [ $days_until_expiry -lt 30 ]; then
                    print_warning "Certificate expires in $days_until_expiry days"
                else
                    print_success "Certificate is valid for $days_until_expiry days"
                fi
            fi
        fi
    else
        print_warning "No SSL certificate information found"
        echo ""
        echo "To generate certificates:"
        echo "  $0 generate-self-signed <domain>"
        echo "  $0 generate-letsencrypt <domain> [email]"
    fi
}

# Function to test SSL configuration
test_ssl() {
    local domain="$1"
    
    echo -e "${CYAN}Testing SSL Configuration${NC}"
    echo ""
    
    # Check if certificates exist
    if [ ! -f "$NGINX_SSL_DIR/cert.pem" ] || [ ! -f "$NGINX_SSL_DIR/key.pem" ]; then
        print_error "SSL certificates not found"
        return 1
    fi
    
    # Test certificate validity
    if openssl x509 -in "$NGINX_SSL_DIR/cert.pem" -noout -checkend 86400; then
        print_success "Certificate is valid"
    else
        print_error "Certificate is invalid or expiring within 24 hours"
    fi
    
    # Test private key
    if openssl rsa -in "$NGINX_SSL_DIR/key.pem" -check -noout 2>/dev/null; then
        print_success "Private key is valid"
    else
        print_error "Private key is invalid"
    fi
    
    # Test certificate-key pair match
    local cert_modulus=$(openssl x509 -noout -modulus -in "$NGINX_SSL_DIR/cert.pem" | openssl md5)
    local key_modulus=$(openssl rsa -noout -modulus -in "$NGINX_SSL_DIR/key.pem" | openssl md5)
    
    if [ "$cert_modulus" = "$key_modulus" ]; then
        print_success "Certificate and private key match"
    else
        print_error "Certificate and private key do not match"
    fi
    
    # Test HTTPS connection if domain is provided
    if [ -n "$domain" ]; then
        echo ""
        print_info "Testing HTTPS connection to $domain..."
        
        # Test various endpoints
        local endpoints=("/health" "/api/v1/health" "/")
        local success=false
        
        for endpoint in "${endpoints[@]}"; do
            print_info "Testing endpoint: https://$domain$endpoint"
            
            # Test with both curl flags for different scenarios
            if curl -s -k --connect-timeout 10 "https://$domain$endpoint" >/dev/null 2>&1; then
                print_success "HTTPS connection successful to $endpoint"
                success=true
                break
            elif curl -s --connect-timeout 10 "https://$domain$endpoint" >/dev/null 2>&1; then
                print_success "HTTPS connection successful to $endpoint (valid certificate)"
                success=true
                break
            fi
        done
        
        if [ "$success" = "false" ]; then
            print_warning "HTTPS connection failed to all endpoints"
            print_info "This is normal if:"
            print_info "- Services are not running"
            print_info "- Domain doesn't resolve to this server"
            print_info "- Firewall is blocking connections"
        fi
        
        # Test SSL/TLS configuration
        echo ""
        print_info "Testing SSL/TLS configuration..."
        
        if command -v openssl &> /dev/null; then
            local ssl_test_result
            ssl_test_result=$(echo | openssl s_client -connect "$domain:443" -servername "$domain" 2>/dev/null)
            
            if echo "$ssl_test_result" | grep -q "Verify return code: 0"; then
                print_success "SSL certificate verification successful"
            elif echo "$ssl_test_result" | grep -q "self signed certificate"; then
                print_warning "Self-signed certificate detected"
            elif echo "$ssl_test_result" | grep -q "unable to verify"; then
                print_warning "Certificate verification failed"
            else
                print_warning "SSL connection test completed (check manually for issues)"
            fi
            
            # Extract and display certificate details
            local cert_subject cert_issuer cert_sans
            cert_subject=$(echo "$ssl_test_result" | grep "subject=" | head -1)
            cert_issuer=$(echo "$ssl_test_result" | grep "issuer=" | head -1)
            cert_sans=$(echo "$ssl_test_result" | grep -A1 "Subject Alternative Name" | tail -1)
            
            if [ -n "$cert_subject" ]; then
                print_info "Certificate Subject: ${cert_subject#*=}"
            fi
            if [ -n "$cert_issuer" ]; then
                print_info "Certificate Issuer: ${cert_issuer#*=}"
            fi
            if [ -n "$cert_sans" ]; then
                print_info "Subject Alternative Names: ${cert_sans}"
            fi
        else
            print_warning "OpenSSL not available for detailed SSL testing"
        fi
    fi
}

# Function to renew certificates
renew_certificates() {
    echo -e "${CYAN}Renewing SSL Certificates${NC}"
    echo ""
    
    local info_file="$SSL_DIR/cert_info.json"
    
    if [ ! -f "$info_file" ]; then
        print_error "No certificate information found"
        return 1
    fi
    
    local cert_type=$(jq -r '.type' "$info_file" 2>/dev/null || echo "unknown")
    local domain=$(jq -r '.domain' "$info_file" 2>/dev/null || echo "unknown")
    
    case $cert_type in
        "letsencrypt")
            print_info "Renewing Let's Encrypt certificate..."
            if certbot renew --nginx; then
                # Copy renewed certificates
                cp "/etc/letsencrypt/live/$domain/fullchain.pem" "$NGINX_SSL_DIR/cert.pem"
                cp "/etc/letsencrypt/live/$domain/privkey.pem" "$NGINX_SSL_DIR/key.pem"
                print_success "Let's Encrypt certificate renewed"
            else
                print_error "Failed to renew Let's Encrypt certificate"
                return 1
            fi
            ;;
        "self-signed")
            print_info "Regenerating self-signed certificate..."
            generate_self_signed "$domain"
            ;;
        *)
            print_error "Unknown certificate type: $cert_type"
            return 1
            ;;
    esac
    
    # Restart nginx to use new certificates
    if docker-compose ps nginx | grep -q "Up"; then
        docker-compose restart nginx
        print_success "Nginx restarted with new certificates"
    fi
}

# Function to validate SSL setup comprehensively
validate_ssl_setup() {
    local domain="${1:-}"
    
    echo -e "${CYAN}Comprehensive SSL Validation${NC}"
    echo ""
    
    # Check if domain is provided
    if [ -z "$domain" ]; then
        local info_file="$SSL_DIR/cert_info.json"
        if [ -f "$info_file" ]; then
            domain=$(jq -r '.domain' "$info_file" 2>/dev/null || echo "")
        fi
        
        if [ -z "$domain" ]; then
            print_error "No domain specified and no certificate information found"
            echo "Usage: $0 validate [domain]"
            return 1
        fi
    fi
    
    print_info "Validating SSL setup for: $domain"
    echo ""
    
    # 1. Certificate file validation
    print_info "1. Checking certificate files..."
    local cert_file="$NGINX_SSL_DIR/cert.pem"
    local key_file="$NGINX_SSL_DIR/key.pem"
    
    if [ ! -f "$cert_file" ]; then
        print_error "Certificate file not found: $cert_file"
        return 1
    else
        print_success "Certificate file exists"
    fi
    
    if [ ! -f "$key_file" ]; then
        print_error "Private key file not found: $key_file"
        return 1
    else
        print_success "Private key file exists"
    fi
    
    # 2. Certificate content validation
    echo ""
    print_info "2. Validating certificate content..."
    
    local cert_valid=true
    if ! openssl x509 -in "$cert_file" -noout -text >/dev/null 2>&1; then
        print_error "Certificate file is corrupted or invalid"
        cert_valid=false
    else
        print_success "Certificate file is valid"
    fi
    
    # 3. Private key validation
    echo ""
    print_info "3. Validating private key..."
    
    if ! openssl rsa -in "$key_file" -check -noout >/dev/null 2>&1; then
        print_error "Private key is invalid"
        cert_valid=false
    else
        print_success "Private key is valid"
    fi
    
    # 4. Certificate-key pair validation
    echo ""
    print_info "4. Checking certificate-key pair match..."
    
    local cert_modulus key_modulus
    cert_modulus=$(openssl x509 -noout -modulus -in "$cert_file" 2>/dev/null | openssl md5 2>/dev/null)
    key_modulus=$(openssl rsa -noout -modulus -in "$key_file" 2>/dev/null | openssl md5 2>/dev/null)
    
    if [ "$cert_modulus" = "$key_modulus" ] && [ -n "$cert_modulus" ]; then
        print_success "Certificate and private key match"
    else
        print_error "Certificate and private key do not match"
        cert_valid=false
    fi
    
    # 5. Certificate expiration check
    echo ""
    print_info "5. Checking certificate expiration..."
    
    if openssl x509 -in "$cert_file" -noout -checkend 86400 >/dev/null 2>&1; then
        local exp_date
        exp_date=$(openssl x509 -in "$cert_file" -noout -enddate 2>/dev/null | cut -d= -f2)
        print_success "Certificate is valid and not expiring within 24 hours"
        print_info "Expires: $exp_date"
    else
        print_warning "Certificate is expiring within 24 hours or already expired"
        cert_valid=false
    fi
    
    # 6. Domain name validation
    echo ""
    print_info "6. Checking certificate domain names..."
    
    local cert_domains
    cert_domains=$(openssl x509 -in "$cert_file" -noout -text 2>/dev/null | grep -A1 "Subject Alternative Name" | tail -1 | tr ',' '\n' | grep DNS: | sed 's/DNS://g' | tr -d ' ')
    
    local cert_cn
    cert_cn=$(openssl x509 -in "$cert_file" -noout -subject 2>/dev/null | sed 's/.*CN=//' | sed 's/,.*//')
    
    local domain_found=false
    if [[ "$cert_cn" == "$domain" ]]; then
        domain_found=true
    fi
    
    if [ -n "$cert_domains" ]; then
        while IFS= read -r cert_domain; do
            if [[ "$cert_domain" == "$domain" ]] || [[ "$cert_domain" == "*.$domain" ]]; then
                domain_found=true
                break
            fi
        done <<< "$cert_domains"
    fi
    
    if [ "$domain_found" = "true" ]; then
        print_success "Certificate is valid for domain: $domain"
    else
        print_warning "Certificate may not be valid for domain: $domain"
        print_info "Certificate CN: $cert_cn"
        if [ -n "$cert_domains" ]; then
            print_info "Certificate SANs: $(echo "$cert_domains" | tr '\n' ', ' | sed 's/,$//')"
        fi
    fi
    
    # 7. DNS resolution check
    echo ""
    print_info "7. Checking DNS resolution..."
    
    if check_domain_resolution "$domain"; then
        print_success "Domain resolves correctly to this server"
    else
        print_warning "Domain resolution issues detected"
        print_info "This may prevent Let's Encrypt validation"
    fi
    
    # 8. Port connectivity check
    echo ""
    print_info "8. Checking port connectivity..."
    
    local ports=(80 443)
    for port in "${ports[@]}"; do
        if nc -z -w5 "$domain" "$port" >/dev/null 2>&1; then
            print_success "Port $port is accessible on $domain"
        elif nc -z -w5 "$(hostname -I | awk '{print $1}')" "$port" >/dev/null 2>&1; then
            print_warning "Port $port is accessible locally but may not be accessible from outside"
        else
            print_warning "Port $port is not accessible"
        fi
    done
    
    # 9. Nginx configuration check
    echo ""
    print_info "9. Checking Nginx configuration..."
    
    if [ -f "./nginx/nginx.conf" ]; then
        if docker run --rm -v "$(pwd)/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:alpine nginx -t >/dev/null 2>&1; then
            print_success "Nginx configuration is valid"
        else
            print_error "Nginx configuration has errors"
            cert_valid=false
        fi
    else
        print_warning "Nginx configuration file not found"
    fi
    
    # 10. Docker Compose validation
    echo ""
    print_info "10. Checking Docker Compose configuration..."
    
    if [ -f "./docker-compose.https.yml" ]; then
        if docker-compose -f docker-compose.yml -f docker-compose.https.yml config >/dev/null 2>&1; then
            print_success "Docker Compose HTTPS configuration is valid"
        else
            print_error "Docker Compose HTTPS configuration has errors"
            cert_valid=false
        fi
    else
        print_warning "Docker Compose HTTPS configuration not found"
    fi
    
    # Summary
    echo ""
    if [ "$cert_valid" = "true" ]; then
        print_success "SSL validation completed successfully!"
        print_info "Your SSL setup appears to be correctly configured"
    else
        print_error "SSL validation found issues that need attention"
        print_info "Please review the errors above and fix them before proceeding"
        return 1
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  generate-self-signed <domain>     Generate self-signed certificate"
    echo "  generate-letsencrypt <domain> [email] [--staging]"
    echo "                                     Generate Let's Encrypt certificate"
    echo "  list                               List current certificate information"
    echo "  test [domain]                      Test SSL configuration"
    echo "  validate [domain]                  Comprehensive SSL setup validation"
    echo "  renew                              Renew existing certificates"
    echo "  help                               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 generate-self-signed api.example.com"
    echo "  $0 generate-letsencrypt api.example.com admin@example.com"
    echo "  $0 generate-letsencrypt api.example.com admin@example.com --staging"
    echo "  $0 test api.example.com"
    echo "  $0 validate api.example.com"
    echo ""
}

# Main function
main() {
    local command="${1:-help}"
    
    case $command in
        generate-self-signed|self-signed)
            if [ $# -lt 2 ]; then
                print_error "Domain name required"
                echo "Usage: $0 generate-self-signed <domain>"
                exit 1
            fi
            
            local domain="$2"
            if ! validate_fqdn "$domain"; then
                print_error "Invalid domain name: $domain"
                exit 1
            fi
            
            print_header
            create_ssl_directories
            generate_self_signed "$domain"
            ;;
            
        generate-letsencrypt|letsencrypt)
            if [ $# -lt 2 ]; then
                print_error "Domain name required"
                echo "Usage: $0 generate-letsencrypt <domain> [email] [--staging]"
                exit 1
            fi
            
            local domain="$2"
            local email="${3:-}"
            local staging="false"
            
            # Check for staging flag
            for arg in "$@"; do
                if [ "$arg" = "--staging" ]; then
                    staging="true"
                    break
                fi
            done
            
            if ! validate_fqdn "$domain"; then
                print_error "Invalid domain name: $domain"
                exit 1
            fi
            
            print_header
            
            # Check domain resolution for Let's Encrypt
            if [ "$staging" = "false" ]; then
                if ! check_domain_resolution "$domain"; then
                    echo ""
                    echo "Domain resolution issues detected. Options:"
                    echo "1. Use staging environment for testing: $0 generate-letsencrypt $domain $email --staging"
                    echo "2. Generate self-signed certificate: $0 generate-self-signed $domain"
                    echo "3. Continue anyway (may fail)"
                    echo ""
                    echo -ne "Continue with Let's Encrypt production? [y/N]: "
                    read -r confirm
                    if [[ ! $confirm =~ ^[Yy] ]]; then
                        print_info "Operation cancelled"
                        exit 0
                    fi
                fi
            fi
            
            create_ssl_directories
            generate_letsencrypt "$domain" "$email" "$staging"
            ;;
            
        list|ls|status)
            print_header
            list_certificates
            ;;
            
        test|check)
            local domain="${2:-}"
            print_header
            test_ssl "$domain"
            ;;
            
        validate)
            local domain="${2:-}"
            print_header
            validate_ssl_setup "$domain"
            ;;
            
        renew|renewal|update)
            print_header
            renew_certificates
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
    
    if ! command -v openssl &> /dev/null; then
        missing_deps+=("openssl")
    fi
    
    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        missing_deps+=("docker-compose")
    fi
    
    if ! command -v nc &> /dev/null && ! command -v ncat &> /dev/null && ! command -v netcat &> /dev/null; then
        missing_deps+=("netcat")
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
#!/bin/bash

# SSL Certificate Monitor Script
# Monitors SSL certificates and sends alerts when they're about to expire

set -e

# Configuration
DOMAIN_NAME="${DOMAIN_NAME:-localhost}"
ALERT_EMAIL="${ALERT_EMAIL:-admin@localhost}"
CHECK_INTERVAL="${CHECK_INTERVAL:-3600}"
ALERT_THRESHOLD="${ALERT_THRESHOLD:-30}"  # Days before expiration to alert
LOG_FILE="/var/log/ssl-monitor/ssl-monitor.log"
CERT_DIR="/etc/letsencrypt/live"
SELF_SIGNED_CERT_DIR="/etc/traefik/certs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

# Check if certificate exists and get expiration date
check_certificate_expiration() {
    local cert_path="$1"
    local cert_type="$2"
    
    if [ ! -f "$cert_path" ]; then
        log "${RED}ERROR: Certificate not found at $cert_path${NC}"
        return 1
    fi
    
    local expiry_date=$(openssl x509 -in "$cert_path" -noout -enddate | cut -d= -f2)
    local expiry_epoch=$(date -d "$expiry_date" +%s)
    local current_epoch=$(date +%s)
    local days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))
    
    log "${BLUE}Certificate Type: $cert_type${NC}"
    log "${BLUE}Certificate Path: $cert_path${NC}"
    log "${BLUE}Expiry Date: $expiry_date${NC}"
    log "${BLUE}Days Until Expiry: $days_until_expiry${NC}"
    
    if [ "$days_until_expiry" -lt "$ALERT_THRESHOLD" ]; then
        log "${RED}WARNING: Certificate expires in $days_until_expiry days!${NC}"
        send_alert "$cert_type" "$expiry_date" "$days_until_expiry"
    elif [ "$days_until_expiry" -lt 0 ]; then
        log "${RED}ERROR: Certificate has already expired!${NC}"
        send_alert "$cert_type" "$expiry_date" "$days_until_expiry"
    else
        log "${GREEN}Certificate is valid for $days_until_expiry more days${NC}"
    fi
    
    return 0
}

# Send alert notification
send_alert() {
    local cert_type="$1"
    local expiry_date="$2"
    local days_until_expiry="$3"
    
    local subject="SSL Certificate Alert - $DOMAIN_NAME"
    local message="SSL Certificate Warning for $DOMAIN_NAME

Certificate Type: $cert_type
Expiry Date: $expiry_date
Days Until Expiry: $days_until_expiry

Please renew the certificate as soon as possible.

This is an automated alert from the SSL Certificate Monitor.
"
    
    # Log alert
    log "${YELLOW}ALERT: Sending notification for $cert_type certificate${NC}"
    
    # Try to send email (requires mail/sendmail to be configured)
    if command -v mail >/dev/null 2>&1; then
        echo "$message" | mail -s "$subject" "$ALERT_EMAIL"
        log "${GREEN}Email alert sent to $ALERT_EMAIL${NC}"
    else
        log "${YELLOW}Mail command not available, logging alert only${NC}"
    fi
    
    # Write alert to file for external monitoring systems
    echo "$message" > "/var/log/ssl-monitor/alert-$(date +%Y%m%d-%H%M%S).txt"
}

# Check SSL/TLS connection to domain
check_ssl_connection() {
    local domain="$1"
    local port="${2:-443}"
    
    log "${BLUE}Checking SSL connection to $domain:$port${NC}"
    
    # Check if we can connect and get certificate info
    if echo | openssl s_client -connect "$domain:$port" -servername "$domain" 2>/dev/null | openssl x509 -noout -dates; then
        log "${GREEN}SSL connection to $domain:$port successful${NC}"
        return 0
    else
        log "${RED}ERROR: Cannot establish SSL connection to $domain:$port${NC}"
        return 1
    fi
}

# Check certificate chain validity
check_certificate_chain() {
    local cert_path="$1"
    
    log "${BLUE}Checking certificate chain for $cert_path${NC}"
    
    # Verify certificate chain
    if openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt "$cert_path" >/dev/null 2>&1; then
        log "${GREEN}Certificate chain is valid${NC}"
        return 0
    else
        log "${YELLOW}Certificate chain verification failed (may be self-signed)${NC}"
        return 1
    fi
}

# Get certificate information
get_certificate_info() {
    local cert_path="$1"
    
    log "${BLUE}Certificate Information for $cert_path:${NC}"
    
    # Subject
    local subject=$(openssl x509 -in "$cert_path" -noout -subject | sed 's/subject=//')
    log "Subject: $subject"
    
    # Issuer
    local issuer=$(openssl x509 -in "$cert_path" -noout -issuer | sed 's/issuer=//')
    log "Issuer: $issuer"
    
    # Serial Number
    local serial=$(openssl x509 -in "$cert_path" -noout -serial | sed 's/serial=//')
    log "Serial: $serial"
    
    # Key Usage
    local key_usage=$(openssl x509 -in "$cert_path" -noout -ext keyUsage 2>/dev/null | grep -v "X509v3 Key Usage" | tr -d ' ')
    log "Key Usage: $key_usage"
    
    # Subject Alternative Names
    local san=$(openssl x509 -in "$cert_path" -noout -ext subjectAltName 2>/dev/null | grep -v "X509v3 Subject Alternative Name" | tr -d ' ')
    log "Subject Alternative Names: $san"
}

# Main monitoring loop
monitor_certificates() {
    log "${GREEN}Starting SSL Certificate Monitor${NC}"
    log "Domain: $DOMAIN_NAME"
    log "Alert Email: $ALERT_EMAIL"
    log "Check Interval: $CHECK_INTERVAL seconds"
    log "Alert Threshold: $ALERT_THRESHOLD days"
    
    while true; do
        log "${BLUE}=== SSL Certificate Check Started ===${NC}"
        
        # Check Let's Encrypt certificate
        if [ -f "$CERT_DIR/$DOMAIN_NAME/cert.pem" ]; then
            log "${BLUE}Checking Let's Encrypt certificate...${NC}"
            check_certificate_expiration "$CERT_DIR/$DOMAIN_NAME/cert.pem" "Let's Encrypt"
            get_certificate_info "$CERT_DIR/$DOMAIN_NAME/cert.pem"
            check_certificate_chain "$CERT_DIR/$DOMAIN_NAME/cert.pem"
        else
            log "${YELLOW}No Let's Encrypt certificate found${NC}"
        fi
        
        # Check self-signed certificate
        if [ -f "$SELF_SIGNED_CERT_DIR/cert.crt" ]; then
            log "${BLUE}Checking self-signed certificate...${NC}"
            check_certificate_expiration "$SELF_SIGNED_CERT_DIR/cert.crt" "Self-Signed"
            get_certificate_info "$SELF_SIGNED_CERT_DIR/cert.crt"
        else
            log "${YELLOW}No self-signed certificate found${NC}"
        fi
        
        # Check SSL connection if domain is not localhost
        if [ "$DOMAIN_NAME" != "localhost" ]; then
            check_ssl_connection "$DOMAIN_NAME"
        fi
        
        log "${BLUE}=== SSL Certificate Check Completed ===${NC}"
        log "Next check in $CHECK_INTERVAL seconds"
        
        sleep "$CHECK_INTERVAL"
    done
}

# Create log directory
mkdir -p "$(dirname "$LOG_FILE")"

# Start monitoring
monitor_certificates
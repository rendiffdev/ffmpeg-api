#!/bin/bash
# Generate self-signed certificate for Traefik default HTTPS

set -e

# Certificate configuration
CERT_DIR="$(dirname "$0")"
DOMAIN="${DOMAIN_NAME:-localhost}"
CERT_DAYS=365

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Generating self-signed certificate for ${DOMAIN}...${NC}"

# Create certificate directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Generate private key
openssl genrsa -out "$CERT_DIR/cert.key" 2048

# Generate certificate signing request
openssl req -new -key "$CERT_DIR/cert.key" -out "$CERT_DIR/cert.csr" \
    -subj "/C=US/ST=State/L=City/O=Rendiff/CN=${DOMAIN}"

# Generate self-signed certificate
openssl x509 -req -days $CERT_DAYS -in "$CERT_DIR/cert.csr" \
    -signkey "$CERT_DIR/cert.key" -out "$CERT_DIR/cert.crt"

# Clean up CSR
rm -f "$CERT_DIR/cert.csr"

# Set appropriate permissions
chmod 644 "$CERT_DIR/cert.crt"
chmod 600 "$CERT_DIR/cert.key"

echo -e "${GREEN}✓ Self-signed certificate generated successfully!${NC}"
echo "  Certificate: $CERT_DIR/cert.crt"
echo "  Private Key: $CERT_DIR/cert.key"
echo "  Valid for: $CERT_DAYS days"
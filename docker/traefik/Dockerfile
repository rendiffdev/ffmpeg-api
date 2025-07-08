FROM traefik:v3.0

# Install OpenSSL for certificate generation
RUN apk add --no-cache openssl

# Create directories
RUN mkdir -p /etc/traefik/certs

# Copy certificate generation script
COPY traefik/certs/generate-self-signed.sh /generate-cert.sh
RUN chmod +x /generate-cert.sh

# Generate self-signed certificate if not exists
RUN if [ ! -f /etc/traefik/certs/cert.crt ]; then \
    cd /etc/traefik/certs && \
    /generate-cert.sh; \
    fi

# Entry point
ENTRYPOINT ["/entrypoint.sh"]
CMD ["traefik"]
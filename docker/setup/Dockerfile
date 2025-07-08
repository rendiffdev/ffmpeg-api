# Setup Container for FFmpeg API
# This container runs the interactive setup wizard

FROM alpine:3.18

# Install required packages
RUN apk add --no-cache \
    bash \
    openssl \
    curl \
    ca-certificates \
    && rm -rf /var/cache/apk/*

# Create app directory
WORKDIR /app

# Copy setup scripts
COPY scripts/interactive-setup.sh /app/scripts/interactive-setup.sh
COPY docker/setup/docker-entrypoint.sh /app/docker-entrypoint.sh

# Copy configuration templates
COPY config/ /app/config/

# Make scripts executable
RUN chmod +x /app/scripts/interactive-setup.sh \
    && chmod +x /app/docker-entrypoint.sh

# Set up non-root user for security
RUN addgroup -g 1000 setup && \
    adduser -u 1000 -G setup -s /bin/bash -D setup

# Switch to non-root user
USER setup

# Set the entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
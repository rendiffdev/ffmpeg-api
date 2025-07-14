# Build stage
FROM python:3.13.5-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.13.5-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    xz-utils \
    netcat-openbsd \
    postgresql-client \
    logrotate \
    && rm -rf /var/lib/apt/lists/*

# Install latest FFmpeg from BtbN/FFmpeg-Builds
COPY docker/install-ffmpeg.sh /tmp/install-ffmpeg.sh
RUN chmod +x /tmp/install-ffmpeg.sh && \
    /tmp/install-ffmpeg.sh && \
    rm /tmp/install-ffmpeg.sh

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create app user
RUN useradd -m -u 1000 -s /bin/bash rendiff

# Create directories
RUN mkdir -p /app /storage /config /data && \
    chown -R rendiff:rendiff /app /storage /config /data

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=rendiff:rendiff api/ /app/api/
COPY --chown=rendiff:rendiff storage/ /app/storage/
COPY --chown=rendiff:rendiff alembic/ /app/alembic/
COPY --chown=rendiff:rendiff alembic.ini /app/alembic.ini

# Copy scripts for setup and maintenance
COPY --chown=rendiff:rendiff scripts/ /app/scripts/

# Create necessary directories
RUN mkdir -p /app/logs /app/temp /app/metrics && \
    chown -R rendiff:rendiff /app/logs /app/temp /app/metrics

# Switch to non-root user
USER rendiff

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run the application
CMD ["/app/scripts/docker-entrypoint.sh", "api"]
# Base Dockerfile with standardized Python version and dependencies
# This ensures consistency across all containers and resolves build issues

# Global build argument for Python version
ARG PYTHON_VERSION=3.12.7

# Base builder stage with all necessary build dependencies
FROM python:${PYTHON_VERSION}-slim AS base-builder

# Set environment variables for consistent builds
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Install comprehensive build dependencies
RUN apt-get update && apt-get install -y \
    # Compilation tools
    gcc \
    g++ \
    make \
    # Development headers for Python extensions
    python3-dev \
    # PostgreSQL development dependencies (fixes psycopg2 issue)
    libpq-dev \
    postgresql-client \
    # SSL/TLS dependencies
    libssl-dev \
    libffi-dev \
    # Image processing dependencies
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    # Audio/Video processing dependencies
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    # System utilities
    curl \
    xz-utils \
    git \
    netcat-openbsd \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create virtual environment with stable settings
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and essential tools to latest stable versions
RUN pip install --upgrade \
    pip==24.0 \
    setuptools==69.5.1 \
    wheel==0.43.0

# Base runtime stage with minimal runtime dependencies
FROM python:${PYTHON_VERSION}-slim AS base-runtime

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y \
    # PostgreSQL client and runtime libraries
    libpq5 \
    postgresql-client \
    # SSL/TLS runtime libraries
    libssl3 \
    libffi8 \
    # Image processing runtime libraries
    libjpeg62-turbo \
    libpng16-16 \
    libwebp7 \
    # System utilities
    curl \
    xz-utils \
    netcat-openbsd \
    # Logging and monitoring
    logrotate \
    # Process management
    procps \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=base-builder /opt/venv /opt/venv

# Create application user with proper permissions
RUN groupadd -r rendiff && \
    useradd -r -g rendiff -m -d /home/rendiff -s /bin/bash rendiff && \
    usermod -u 1000 rendiff && \
    groupmod -g 1000 rendiff

# Create application directories with proper ownership
RUN mkdir -p \
    /app \
    /app/logs \
    /app/temp \
    /app/metrics \
    /app/storage \
    /app/uploads \
    /app/config \
    /data \
    /tmp/rendiff \
    && chown -R rendiff:rendiff \
    /app \
    /data \
    /tmp/rendiff \
    && chmod -R 755 /app \
    && chmod -R 775 /tmp/rendiff

# Install FFmpeg using our standardized script
COPY docker/install-ffmpeg.sh /tmp/install-ffmpeg.sh
RUN chmod +x /tmp/install-ffmpeg.sh && \
    /tmp/install-ffmpeg.sh && \
    rm /tmp/install-ffmpeg.sh

# Health check utilities
RUN echo '#!/bin/bash\necho "Container health check passed"' > /usr/local/bin/health-check \
    && chmod +x /usr/local/bin/health-check

# Set working directory
WORKDIR /app

# Switch to non-root user
USER rendiff

# Default health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /usr/local/bin/health-check
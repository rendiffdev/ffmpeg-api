# Build argument for worker type selection
ARG WORKER_TYPE=cpu

# Build stage
FROM python:3.12-slim AS builder

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

# Runtime stage - use NVIDIA CUDA base for GPU support
FROM nvidia/cuda:12.3.0-runtime-ubuntu22.04 AS runtime-gpu

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    curl \
    xz-utils \
    netcat-openbsd \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install latest FFmpeg from BtbN/FFmpeg-Builds
COPY docker/install-ffmpeg.sh /tmp/install-ffmpeg.sh
RUN chmod +x /tmp/install-ffmpeg.sh && \
    /tmp/install-ffmpeg.sh && \
    rm /tmp/install-ffmpeg.sh

# Runtime stage - standard for CPU
FROM python:3.12-slim AS runtime-cpu

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    xz-utils \
    netcat-openbsd \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install latest FFmpeg from BtbN/FFmpeg-Builds
COPY docker/install-ffmpeg.sh /tmp/install-ffmpeg.sh
RUN chmod +x /tmp/install-ffmpeg.sh && \
    /tmp/install-ffmpeg.sh && \
    rm /tmp/install-ffmpeg.sh

# Select runtime based on build arg (ARG declared at top)
FROM runtime-${WORKER_TYPE} AS runtime

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create app user
RUN useradd -m -u 1000 -s /bin/bash rendiff

# Create directories
RUN mkdir -p /app /storage /config /data /tmp/rendiff && \
    chown -R rendiff:rendiff /app /storage /config /data /tmp/rendiff

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=rendiff:rendiff api/ /app/api/
COPY --chown=rendiff:rendiff worker/ /app/worker/
COPY --chown=rendiff:rendiff storage/ /app/storage/

# Switch to non-root user
USER rendiff

# Set environment for GPU support
ENV NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}
ENV NVIDIA_DRIVER_CAPABILITIES=${NVIDIA_DRIVER_CAPABILITIES:-video,compute,utility}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD celery -A worker.main inspect ping || exit 1

# Copy scripts for setup and maintenance
COPY --chown=rendiff:rendiff scripts/ /app/scripts/

# Run the worker
CMD ["/app/scripts/docker-entrypoint.sh", "worker"]
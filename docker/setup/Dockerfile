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

# Runtime stage
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create app user
RUN useradd -m -u 1000 -s /bin/bash rendiff

# Create directories
RUN mkdir -p /app /etc/rendiff /setup && \
    chown -R rendiff:rendiff /app /etc/rendiff /setup

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=rendiff:rendiff setup/ /app/setup/
COPY --chown=rendiff:rendiff api/ /app/api/
COPY --chown=rendiff:rendiff config/ /app/config/

# Switch to non-root user
USER rendiff

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import setup.wizard; print('Setup wizard available')" || exit 1

# Run the setup wizard
CMD ["python", "-m", "setup.wizard"]
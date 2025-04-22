# Use Docker BuildKit syntax v1.3+ for multi‐arch args
# syntax=docker/dockerfile:1.3

########################################
# 1. Builder stage: install deps & FFmpeg
########################################
FROM python:3.10-slim AS builder

# Declare the build platform variable
ARG TARGETPLATFORM

# Install tools for download & extraction
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      curl xz-utils ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /home/ffapi/app

# Python deps
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY . .

# Download & extract correct FFmpeg build
RUN set -eux; \
    case "${TARGETPLATFORM}" in \
      "linux/amd64") ARCH="amd64" ;; \
      "linux/arm64") ARCH="arm64" ;; \
      *) echo "Unsupported platform ${TARGETPLATFORM}" >&2; exit 1 ;; \
    esac; \
    URL="https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-git-${ARCH}-static.tar.xz"; \
    echo "Downloading FFmpeg from ${URL}"; \
    curl -fL "${URL}" -o /tmp/ffmpeg.tar.xz; \
    mkdir -p /tmp/ffmpeg; \
    tar -xJf /tmp/ffmpeg.tar.xz -C /tmp/ffmpeg --strip-components=1; \
    install -m755 /tmp/ffmpeg/ffmpeg  /usr/local/bin/ffmpeg; \
    install -m755 /tmp/ffmpeg/ffprobe /usr/local/bin/ffprobe; \
    install -m755 /tmp/ffmpeg/ffplay  /usr/local/bin/ffplay; \
    rm -rf /tmp/ffmpeg /tmp/ffmpeg.tar.xz

########################################
# 2. Runtime stage
########################################
FROM python:3.10-slim

RUN useradd -m ffapi

WORKDIR /home/ffapi/app

# Copy over static FFmpeg binaries
COPY --from=builder /usr/local/bin/ffmpeg  /usr/local/bin/ffmpeg
COPY --from=builder /usr/local/bin/ffprobe /usr/local/bin/ffprobe
COPY --from=builder /usr/local/bin/ffplay  /usr/local/bin/ffplay

# Copy Python packages
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Copy application code
COPY . .

RUN chown -R ffapi:ffapi /home/ffapi/app

USER ffapi
EXPOSE 8000

ENTRYPOINT ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]

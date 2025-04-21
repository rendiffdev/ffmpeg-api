# Dockerfile
FROM python:3.10-slim AS builder

# Install deps for ffmpeg extraction
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    curl xz-utils \
  && rm -rf /var/lib/apt/lists/*

# Pick up code
WORKDIR /home/ffapi/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Download BtbN static FFmpeg build per architecture
# BuildKit will set TARGETPLATFORM, so we can choose the correct binary
RUN set -eux; \
    case "${TARGETPLATFORM}" in \
      "linux/amd64") ARCH="amd64" ;; \
      "linux/arm64") ARCH="arm64" ;; \
      *) echo "Unsupported platform ${TARGETPLATFORM}" >&2; exit 1 ;; \
    esac; \
    FFBIN="ffmpeg-git-${ARCH}-static.tar.xz"; \
    echo "Downloading ${FFBIN}"; \
    curl -L \
      "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/${FFBIN}" \
      -o /tmp/${FFBIN}; \
    tar -xJf /tmp/${FFBIN} -C /usr/local/bin --strip-components=1; \
    rm /tmp/${FFBIN}

# Runtime image
FROM python:3.10-slim

RUN useradd -m ffapi

WORKDIR /home/ffapi/app

# copy ffmpeg binaries + Python deps + app code
COPY --from=builder /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=builder /usr/local/bin/ffprobe /usr/local/bin/ffprobe
COPY --from=builder /usr/local/bin/ffplay /usr/local/bin/ffplay
# (VMAF binary if needed—you can optionally download it similarly)
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

COPY . .

# Ensure our ffapi user owns everything
RUN chown -R ffapi:ffapi /home/ffapi/app

USER ffapi
EXPOSE 8000

ENTRYPOINT ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]

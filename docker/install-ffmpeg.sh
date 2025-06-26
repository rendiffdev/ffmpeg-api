#!/bin/bash
# Install FFmpeg from BtbN/FFmpeg-Builds in Docker containers

set -e

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        FFMPEG_ARCH="linux64"
        ;;
    aarch64|arm64)
        FFMPEG_ARCH="linuxarm64"
        ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

# Download URL
RELEASE_URL="https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest"
ASSET_NAME="ffmpeg-master-latest-${FFMPEG_ARCH}-gpl.tar.xz"

echo "Installing FFmpeg for $ARCH architecture..."

# Get download URL from latest release
DOWNLOAD_URL=$(curl -s $RELEASE_URL | grep "browser_download_url.*${ASSET_NAME}" | cut -d '"' -f 4)

if [ -z "$DOWNLOAD_URL" ]; then
    echo "Failed to find download URL for $ASSET_NAME"
    exit 1
fi

echo "Downloading from: $DOWNLOAD_URL"

# Create temporary directory
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR

# Download and extract
curl -L -o ffmpeg.tar.xz "$DOWNLOAD_URL"
tar -xf ffmpeg.tar.xz

# Find extracted directory
FFMPEG_DIR=$(find . -maxdepth 1 -type d -name 'ffmpeg-*' | head -1)

if [ -z "$FFMPEG_DIR" ]; then
    echo "Failed to find extracted FFmpeg directory"
    exit 1
fi

# Install binaries
mkdir -p /usr/local/bin
cp -f $FFMPEG_DIR/bin/ffmpeg /usr/local/bin/
cp -f $FFMPEG_DIR/bin/ffprobe /usr/local/bin/
[ -f $FFMPEG_DIR/bin/ffplay ] && cp -f $FFMPEG_DIR/bin/ffplay /usr/local/bin/

# Make executable
chmod +x /usr/local/bin/ff*

# Copy documentation
mkdir -p /usr/local/share/ffmpeg
cp -rf $FFMPEG_DIR/doc /usr/local/share/ffmpeg/ 2>/dev/null || true
cp -f $FFMPEG_DIR/LICENSE* /usr/local/share/ffmpeg/ 2>/dev/null || true

# Save version info
cat > /usr/local/share/ffmpeg/version.json <<EOF
{
  "source": "BtbN/FFmpeg-Builds",
  "asset": "${ASSET_NAME}",
  "download_url": "${DOWNLOAD_URL}",
  "installed_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "architecture": "${ARCH}"
}
EOF

# Cleanup
cd /
rm -rf $TEMP_DIR

# Verify installation
echo "Verifying FFmpeg installation..."
ffmpeg -version

echo "FFmpeg installation complete!"
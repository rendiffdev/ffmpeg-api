# FFmpeg API Service

> **Open‑source**, **production‑grade**, Dockerized REST API exposing FFmpeg, ffprobe and quality‑metrics (VMAF, PSNR, SSIM) for video, image and audio workflows.


## Features

- **Authentication**: JWT tokens via `/api/v1/auth/token`  
- **Asynchronous Jobs**: Job IDs, status, logs, errors, elapsed time  
- **Location Abstraction**: Local filesystem or AWS S3 URLs for input/output  
- **Video**  
  - Transcode to H.264, HEVC, VP9, AV1  
  - Quality metrics: VMAF, PSNR, SSIM  
  - Scaling, frame‑rate conversion, HDR & color‑space  
  - HLS & DASH packaging  
  - Burn‑in subtitles (SRT/VTT)  
  - Thumbnail and preview sprite generation  
- **Image**  
  - Resize, crop, filters (grayscale, blur, etc.)  
  - Watermark overlay  
  - Format conversion: JPEG, PNG, WebP, AVIF  
- **Audio**  
  - Convert to AAC, Opus, MP3, WAV  
  - Bitrate/sample‑rate adjustments, mono/stereo  
  - Loudness normalization (EBU R128)  
- **Invoke FFmpeg Locally or Remotely** via SSH  
- **AWS S3 Integration** for scalable storage  

---

## Prerequisites

- **Docker** (Engine & Compose) or **Python 3.10+**  
- **FFmpeg**, **ffprobe**, **ffmpeg‑quality‑metrics** installed on host or remote server  
- (Optional) AWS credentials with S3 read/write permissions  

---

## One‑Time-Setup

Instead of manually editing `.env`, run the interactive installer:

```bash
chmod +x setup.py
./setup.py
```

You’ll be prompted for:

- **FFmpeg** binary paths or SSH details  
- **AWS S3** access key, secret, region (if using S3)  
- **JWT** secret key and expiry  
- **API Host**, **Port**, **Worker count**

This generates a `.env` file consumed by the service.

---

## Configuration

Copy the example and verify:

```bash
cp config/example.env .env
# Or edit the generated .env from setup.py
```

Key environment variables:

```ini
# API server
HOST=0.0.0.0
PORT=8000
WORKERS=4

# FFmpeg binaries
FFMPEG_PATH=/usr/bin/ffmpeg
FFPROBE_PATH=/usr/bin/ffprobe
VMAF_PATH=/usr/local/bin/ffmpeg-quality-metrics
MODE=local        # or ssh
# SSH_HOST=...
# SSH_USER=...
# SSH_KEY_PATH=...

# AWS S3 (optional)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# JWT auth
SECRET_KEY=your_secure_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```  

---

## Docker Deployment

Build and run the container:

```bash
docker build -t ffmpeg-api-service:latest .
docker run -d --name ffapi \
  --env-file .env \
  -v /usr/bin/ffmpeg:/usr/bin/ffmpeg:ro \
  -p 8000:8000 \
  ffmpeg-api-service:latest
```

> **Note**: Mount your ffmpeg binaries into the container if installed on host.

---

## Local Development

```bash
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 --workers 4
```

---

## Running Tests

Place sample fixtures in `tests/fixtures/`:

- `test.mp4` (small video)  
- `test.jpg`  
- `test.wav`  

Then:

```bash
pytest --maxfail=1 --disable-warnings -q
```

---

## Authentication

Obtain a bearer token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -F "username=user@example.com" \
  -F "password=password"
```

Response:

```json
{ "access_token":"<JWT>", "token_type":"bearer" }
```

Include in subsequent requests:

```
Authorization: Bearer <JWT>
```

---

## API Endpoints

### Video Endpoints

#### POST /api/v1/video/transcode

Async video transcode job.

**Body**:

```json
{
  "input":   { "local_path": "/tmp/in.mp4", "s3_path": null },
  "output":  { "local_path": "/tmp/out.mp4", "s3_path": null },
  "codec":   "h264",
  "crf":     23,
  "preset":  "medium"
}
```

**Response**:

```json
{ "job_id": "abcdef123456" }
```

#### GET /api/v1/video/jobs/{job_id}

Check job status.

**Response**:

```json
{
  "id": "abcdef123456",
  "status": "RUNNING|SUCCESS|FAILED",
  "log": "...",
  "error": "...",
  "time_taken": 12.345
}
```

#### POST /api/v1/video/quality

Compute quality metrics.

**Body**:

```json
{
  "reference": { "local_path":"ref.mp4", "s3_path": null },
  "distorted": { "local_path":"dist.mp4", "s3_path": null },
  "metrics": ["vmaf","psnr","ssim"]
}
```

**Response**:

```json
{ "vmaf":"...", "psnr":"...", "ssim":"..." }
```

### Image Endpoints

#### POST /api/v1/image/process

Async image processing job.

**Body**:

```json
{
  "input": {
    "local_path": "tests/fixtures/test.jpg",
    "s3_path": null
  },
  "output": {
    "local_path": "tests/fixtures/out.jpg",
    "s3_path": null
  },
  "operations": [
    { "type":"resize",    "params":{ "width":100, "height":100 } },
    { "type":"filter",    "params":{ "name":"grayscale" } }
  ]
}
```

**Response**:

```json
{ "job_id":"abcdef123456" }
```

#### GET /api/v1/image/jobs/{job_id}

Check image job status.

### Audio Endpoints

#### POST /api/v1/audio/convert

Async audio conversion job.

**Body**:

```json
{
  "input": { "local_path":"in.wav", "s3_path":null },
  "output": { "local_path":"out.aac", "s3_path":null },
  "target_codec":"aac",
  "bitrate":"64k",
  "sample_rate":44100,
  "channels":2
}
```

**Response**:

```json
{ "job_id":"abcdef123456" }
```

#### GET /api/v1/audio/jobs/{job_id}

Check audio job status.

---

## Continuous Integration

The repository includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that:

1. Checks out code
2. Sets up Python 3.10
3. Installs dependencies & runs tests
4. Builds a multi-arch Docker image
5. Optionally pushes to GitHub Container Registry

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

This project is licensed under the **MIT License**.


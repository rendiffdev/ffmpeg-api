# Rendiff API Documentation

Complete API reference for the Rendiff FFmpeg API service.

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Core Endpoints](#core-endpoints)
4. [Job Management](#job-management)
5. [Error Handling](#error-handling)
6. [Examples](#examples)
7. [SDKs](#sdks)

## Overview

The Rendiff API provides a RESTful interface to FFmpeg's media processing capabilities. All API requests should be made to:

```
http://your-server:8080/api/v1
```

### Base URL Structure

- Development: `http://localhost:8080/api/v1`
- Production: `https://your-domain.com/api/v1`

### Content Type

All requests and responses use JSON:
```
Content-Type: application/json
```

## Authentication

### API Key Authentication

Include your API key in the request header:

```http
X-API-Key: your-api-key-here
```

Or use Bearer token:

```http
Authorization: Bearer your-api-key-here
```

### Obtaining API Keys

For self-hosted installations, API keys are managed locally. By default, any non-empty key is accepted. In production, implement proper key management.

## Core Endpoints

### Convert Media

Universal endpoint for all media conversion operations.

```http
POST /api/v1/convert
```

#### Basic Conversion

```json
{
  "input": "/storage/input/video.mov",
  "output": "mp4"
}
```

#### Advanced Conversion

```json
{
  "input": {
    "path": "s3://bucket/input/video.mov",
    "credentials": "presigned"
  },
  "output": {
    "path": "/storage/output/final.mp4",
    "format": "mp4",
    "video": {
      "codec": "h264",
      "preset": "medium",
      "crf": 23,
      "resolution": "1920x1080",
      "fps": 30
    },
    "audio": {
      "codec": "aac",
      "bitrate": "192k",
      "channels": 2,
      "normalize": true
    }
  },
  "operations": [
    {
      "type": "trim",
      "start": 10,
      "duration": 60
    },
    {
      "type": "watermark",
      "image": "/storage/assets/logo.png",
      "position": "bottom-right",
      "opacity": 0.8
    }
  ],
  "options": {
    "priority": "high",
    "hardware_acceleration": "auto",
    "webhook_url": "https://your-app.com/webhook"
  }
}
```

#### Response

```json
{
  "job": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "queued",
    "priority": "high",
    "progress": 0,
    "stage": "queued",
    "created_at": "2025-01-27T10:00:00Z",
    "links": {
      "self": "/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000",
      "events": "/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/events",
      "logs": "/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/logs"
    }
  }
}
```

### Analyze Media

Analyze media files for quality metrics without conversion.

```http
POST /api/v1/analyze
```

```json
{
  "input": "/storage/input/video.mp4",
  "reference": "/storage/reference/original.mp4",
  "metrics": ["vmaf", "psnr", "ssim"]
}
```

### Create Streaming Format

Generate HLS or DASH streaming formats.

```http
POST /api/v1/stream
```

```json
{
  "input": "/storage/input/video.mp4",
  "output": "/storage/output/stream",
  "type": "hls",
  "variants": [
    {"resolution": "1080p", "bitrate": "5M"},
    {"resolution": "720p", "bitrate": "2.5M"},
    {"resolution": "480p", "bitrate": "1M"}
  ],
  "segment_duration": 6
}
```

### Estimate Job

Get time and resource estimates without creating a job.

```http
POST /api/v1/estimate
```

```json
{
  "input": "/storage/input/video.mp4",
  "output": "mp4",
  "operations": [{"type": "resize", "resolution": "4k"}]
}
```

Response:
```json
{
  "estimated": {
    "duration_seconds": 300,
    "output_size_bytes": 524288000
  },
  "resources": {
    "cpu_cores": 4,
    "memory_gb": 8,
    "gpu_required": false
  }
}
```

## Job Management

### List Jobs

```http
GET /api/v1/jobs?status=processing&page=1&per_page=20&sort=created_at:desc
```

Parameters:
- `status`: Filter by status (queued, processing, completed, failed, cancelled)
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 20, max: 100)
- `sort`: Sort field and order (e.g., "created_at:desc")

### Get Job Details

```http
GET /api/v1/jobs/{job_id}
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45.5,
  "stage": "encoding",
  "fps": 24.5,
  "eta_seconds": 180,
  "created_at": "2025-01-27T10:00:00Z",
  "started_at": "2025-01-27T10:01:00Z",
  "progress_details": {
    "percentage": 45.5,
    "stage": "encoding",
    "fps": 24.5,
    "quality": {
      "vmaf": 94.5,
      "psnr": 42.1
    }
  }
}
```

### Cancel Job

```http
DELETE /api/v1/jobs/{job_id}
```

### Stream Progress Events

Real-time progress updates via Server-Sent Events.

```http
GET /api/v1/jobs/{job_id}/events
```

Example events:
```
event: progress
data: {"percentage": 25.5, "stage": "encoding", "fps": 48.5, "eta_seconds": 240}

event: progress
data: {"percentage": 50.0, "stage": "encoding", "fps": 52.1, "eta_seconds": 120}

event: complete
data: {"status": "completed", "output_path": "/storage/output/final.mp4"}
```

### Get Job Logs

```http
GET /api/v1/jobs/{job_id}/logs?lines=100
```

## Error Handling

### Error Response Format

```json
{
  "error": {
    "type": "validation_error",
    "code": "INVALID_CODEC_FORMAT",
    "message": "Codec 'vp9' is incompatible with format 'mp4'",
    "details": {
      "field": "output.video.codec",
      "value": "vp9",
      "allowed": ["h264", "h265"],
      "suggestion": "Use 'webm' format or change codec to 'h264'"
    },
    "doc_url": "https://docs.rendiff.com/errors/INVALID_CODEC_FORMAT",
    "request_id": "req_8g4f5e3b2c0d"
  }
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `INVALID_INPUT` | Input file not found or invalid |
| `INVALID_OUTPUT` | Output path or format invalid |
| `CODEC_MISMATCH` | Codec incompatible with container |
| `INSUFFICIENT_RESOURCES` | Not enough resources to process |
| `QUOTA_EXCEEDED` | API quota limit reached |
| `JOB_NOT_FOUND` | Job ID does not exist |
| `ACCESS_DENIED` | No permission to access resource |

## Examples

### Example 1: Simple MP4 Conversion

```bash
curl -X POST http://localhost:8080/api/v1/convert \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input": "/storage/input/video.avi",
    "output": "mp4"
  }'
```

### Example 2: Resize Video

```bash
curl -X POST http://localhost:8080/api/v1/convert \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input": "/storage/input/video.mp4",
    "output": {
      "path": "/storage/output/video_720p.mp4",
      "video": {"resolution": "1280x720"}
    }
  }'
```

### Example 3: Extract Audio

```bash
curl -X POST http://localhost:8080/api/v1/convert \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input": "/storage/input/video.mp4",
    "output": {
      "path": "/storage/output/audio.mp3",
      "format": "mp3"
    }
  }'
```

### Example 4: Create HLS Stream

```bash
curl -X POST http://localhost:8080/api/v1/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input": "/storage/input/video.mp4",
    "output": "/storage/output/stream",
    "type": "hls",
    "variants": [
      {"resolution": "720p", "bitrate": "2M"},
      {"resolution": "480p", "bitrate": "1M"}
    ]
  }'
```

## SDKs

### Python SDK

```python
from rendiff import RendiffClient

client = RendiffClient(api_key="your-api-key", base_url="http://localhost:8080")

# Simple conversion
job = client.convert(
    input="/storage/input/video.avi",
    output="mp4"
)

# Monitor progress
for progress in job.watch():
    print(f"Progress: {progress.percentage}%")

# Get result
result = job.wait()
print(f"Output: {result.output_path}")
```

### JavaScript SDK

```javascript
import { RendiffClient } from '@rendiff/sdk';

const client = new RendiffClient({
  apiKey: 'your-api-key',
  baseUrl: 'http://localhost:8080'
});

// Convert with async/await
const job = await client.convert({
  input: '/storage/input/video.avi',
  output: 'mp4'
});

// Watch progress
job.onProgress((progress) => {
  console.log(`Progress: ${progress.percentage}%`);
});

// Wait for completion
const result = await job.wait();
console.log(`Output: ${result.outputPath}`);
```

### cURL Examples

See the [examples directory](../examples/) for more cURL examples and use cases.

## Rate Limiting

Default rate limits per API key:
- 10 requests/second
- 1000 requests/hour
- 10 concurrent jobs

These can be configured in the KrakenD gateway configuration.

## Webhooks

Configure webhooks to receive job updates:

```json
{
  "webhook_url": "https://your-app.com/webhook",
  "webhook_events": ["progress", "complete", "error"]
}
```

Webhook payload:
```json
{
  "event": "progress",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-01-27T10:05:00Z",
  "data": {
    "percentage": 75.5,
    "stage": "encoding",
    "fps": 45.2
  }
}
```

## Support

- API Documentation: http://localhost:8080/docs
- OpenAPI Schema: http://localhost:8080/openapi.json
- GitHub: https://github.com/rendiff/rendiff
- Discord: https://discord.gg/rendiff
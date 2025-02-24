# FFmpeg as APIs v0.1

A **containerized** FastAPI microservice that exposes [FFmpeg](https://ffmpeg.org/) capabilities via a **REST API**. This service supports **advanced codecs** (VP9, AV1, H.265, etc.), **streaming formats** (HLS, DASH), **API key-based authentication**, **webhook** notifications, and **background processing** for large jobs.

---

## Table of Contents

- [Features](#features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Authentication](#authentication)
  - [Endpoints](#endpoints)
  - [Example Requests](#example-requests)
- [Advanced Topics](#advanced-topics)
  - [Asynchronous Jobs](#asynchronous-jobs)
  - [Webhook Integration](#webhook-integration)
  - [API Key Management](#api-key-management)
- [Development](#development)
  - [Run Locally](#run-locally)
  - [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Advanced Codec Support**: Transcode using VP9, AV1, H.265, and more.  
- **Streaming Outputs**: Generate HLS (`.m3u8`) and DASH (`.mpd`) playlists.  
- **API Key-Based Authentication**: Restrict access to authorized users.  
- **Asynchronous Processing**: Offload long-running transcoding jobs to background tasks.  
- **Webhook Notifications**: Receive completion or failure events via Hook0 or similar.  
- **Dockerized**: Easily deployable on any container platform (Kubernetes, Docker Swarm, ECS, etc.).

---

## Getting Started

### Prerequisites

- Docker installed on your system.
- (Optional) A valid [Hook0](https://hook0.com/) webhook URL if you want asynchronous notifications.
- (Optional) A database connection if you want to store and manage multiple API keys.  
  (By default, you can use a single key from an environment variable.)

### Installation

1. **Pull the Docker Image**  
   ```bash
   docker pull rendiff/ffmpeg-api
   ```

2. **Run the Docker Container**  
   ```bash
   docker run -p 3000:3000 \
     -e FFMPEG_API_KEY="MY_SUPER_SECRET_KEY" \
     rendiff/ffmpeg-api
   ```

   - The server listens on port `3000` by default; you can map it to any external port.

---

## Configuration

| Environment Variable       | Description                                                           | Default Value            |
|----------------------------|-----------------------------------------------------------------------|--------------------------|
| `FFMPEG_API_KEY`           | **Required**. The single API key that grants access to protected APIs.| `MY_SUPER_SECRET_KEY`    |
| `WEBHOOK_TIMEOUT`          | Optional. Max time (in seconds) for webhook call.                     | 10                       |
| `ENABLE_ASYNC`            | Enable asynchronous job handling (`true/false`).                      | `false`                  |
| `WORKER_COUNT`             | Number of Gunicorn workers to run.                                    | 2                        |
| `LOG_LEVEL`                | Set logging level (`debug`, `info`, `warning`, `error`).              | `info`                   |

---

## Usage

### Authentication

All protected endpoints require an **API key**. By default, this is passed in the `X-API-Key` header. For example:

```bash
curl -X POST \
  -H "X-API-Key: MY_SUPER_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input":"input.mp4","output":"output.webm"}' \
  http://localhost:3000/api/v1/transcode
```

> **Note**: For production deployments, always use **HTTPS** to avoid sending keys in plain text.

### Endpoints

1. **`POST /api/v1/transcode`**  
   - Transcode or convert media to a desired format/codec.  
   - Body parameters include `input`, `output`, `codec`, `format`, `options`, `webhookUrl`.

2. **`POST /api/v1/probe`**  
   - Get metadata (duration, bitrate, codec info) of a media file.

3. **`GET /api/v1/job/{jobId}`**  
   - Retrieve the status of a previously submitted transcoding job.

4. **`GET /api/v1/health`**  
   - Health check endpoint (may or may not require an API key, based on config).

### Example Requests

1. **Convert MP4 to VP9 (WebM)**  
   ```bash
   curl -X POST http://localhost:3000/api/v1/transcode \
     -H "Content-Type: application/json" \
     -H "X-API-Key: MY_SUPER_SECRET_KEY" \
     -d '{
       "input": "input.mp4",
       "output": "output.webm",
       "format": "webm",
       "codec": "vp9",
       "options": {
         "bitrate": "1000k",
         "crf": 30,
         "preset": "slow"
       }
     }'
   ```

2. **Generate HLS**  
   ```bash
   curl -X POST http://localhost:3000/api/v1/transcode \
     -H "Content-Type: application/json" \
     -H "X-API-Key: MY_SUPER_SECRET_KEY" \
     -d '{
       "input": "input.mp4",
       "output": "output.m3u8",
       "format": "hls",
       "codec": "h264",
       "options": {
         "bitrate": "2500k",
         "preset": "fast",
         "segment_time": 4
       }
     }'
   ```

3. **Metadata Probe**  
   ```bash
   curl -X POST http://localhost:3000/api/v1/probe \
     -H "Content-Type: application/json" \
     -H "X-API-Key: MY_SUPER_SECRET_KEY" \
     -d '{
       "input": "input.mp4"
     }'
   ```

---

## Advanced Topics

### Asynchronous Jobs

If `ENABLE_ASYNC=true`, the service can offload transcoding tasks to a background worker (e.g., using Celery, RQ, or FastAPI’s native background tasks). The endpoint immediately returns a `jobId` with status `pending`, and the job runs in the background.  
- **Check Status**: Use `GET /api/v1/job/{jobId}` or a webhook notification.

### Webhook Integration

Optionally include a `webhookUrl` in your `POST /api/v1/transcode` body. When the job finishes (success or failure), the service will `POST` a JSON payload to that URL, for example:

```json
{
  "jobId": "1234-5678",
  "status": "completed",
  "output": "output.m3u8",
  "duration": 95
}
```

### API Key Management

- **Single Key**: By default, read from `FFMPEG_API_KEY`.  
- **Multiple Keys**: Store keys in a database and modify the authentication middleware to look them up.  
- **Rotation**: Generate a new key (e.g., `secrets.token_hex(32)`) and mark the old key as invalid in your storage layer.  
- **Revocation**: Mark a key as inactive or remove it from the data store.

---

## Development

### Run Locally

1. **Clone Repo & Install Dependencies**  
   ```bash
   git clone https://github.com/yourusername/ffmpeg-api.git
   cd ffmpeg-api
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**  
   ```bash
   export FFMPEG_API_KEY="MY_DEVELOPMENT_KEY"
   ```

3. **Start Server**  
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 3000
   ```
   - Access API at `http://localhost:3000`.

### Testing

- **Unit Tests**:  
  ```bash
  pytest
  ```
- **Integration Tests**:  
  - Some tests may require actual FFmpeg binaries and sample media files.

---

## Contributing

Contributions are welcome! Feel free to open a [pull request](https://github.com/yourusername/ffmpeg-api/pulls) or [issue](https://github.com/yourusername/ffmpeg-api/issues) for improvements, bug fixes, or feature requests.

**Guidelines**:
- Fork the repository and create a feature branch.
- Write unit/integration tests if possible.
- Submit a pull request with a clear description of changes.

---

## License

[MIT License](LICENSE)  
This project is licensed under the terms of the MIT license.  

---

> **Note**: The Docker image, environment variables, and example commands are subject to change. Always refer to the latest tagged release and documentation for stable configurations.

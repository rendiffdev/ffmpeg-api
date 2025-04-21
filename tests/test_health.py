from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)

def test_video_health():
    r=client.get("/api/v1/video/health"); assert r.status_code==200; assert r.json()["status"]=="ok"

def test_image_health():
    r=client.get("/api/v1/image/health"); assert r.status_code==200; assert r.json()["status"]=="ok"

def test_audio_health():
    r=client.get("/api/v1/audio/health"); assert r.status_code==200; assert r.json()["status"]=="ok"

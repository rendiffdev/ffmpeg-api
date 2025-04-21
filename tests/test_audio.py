from fastapi.testclient import TestClient
from tests.utils import get_test_token
client=TestClient(__import__('app.main',fromlist=['app']).app)

def test_audio_convert_job():
    token=get_test_token()
    req={
        "input":{"local_path":"tests/fixtures/test.wav","s3_path":None},
        "output":{"local_path":"tests/fixtures/out.aac","s3_path":None},
        "target_codec":"aac","bitrate":"64k","sample_rate":44100,"channels":1
    }
    r=client.post("/api/v1/audio/convert",json=req,headers={"Authorization":f"Bearer {token}"});assert r.status_code==200;assert"job_id"in r.json()

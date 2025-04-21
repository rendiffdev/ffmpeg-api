from fastapi.testclient import TestClient
from tests.utils import get_test_token
client=TestClient(__import__('app.main',fromlist=['app']).app)

def test_video_transcode_job():
    token=get_test_token()
    req={
        "input":{"local_path":"tests/fixtures/test.mp4","s3_path":None},
        "output":{"local_path":"tests/fixtures/out.mp4","s3_path":None},
        "codec":"h264","crf":23,"preset":"medium"
    }
    r=client.post("/api/v1/video/transcode",json=req,headers={"Authorization":f"Bearer {token}"});assert r.status_code==200;assert"job_id"in r.json()

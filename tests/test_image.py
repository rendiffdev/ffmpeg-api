from fastapi.testclient import TestClient
from tests.utils import get_test_token
client=TestClient(__import__('app.main',fromlist=['app']).app)

def test_image_process_job():
    token=get_test_token()
    req={
        "input":{"local_path":"tests/fixtures/test.jpg","s3_path":None},
        "output":{"local_path":"tests/fixtures/out.jpg","s3_path":None},
        "operations":[{"type":"resize","params":{"width":10,"height":10}}]
    }
    r=client.post("/api/v1/image/process",json=req,headers={"Authorization":f"Bearer {token}"});assert r.status_code==200;assert"job_id"in r.json()

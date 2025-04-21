from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
def get_test_token():
    r=client.post("/api/v1/auth/token",data={"username":"user@example.com","password":"password"})
    r.raise_for_status()
    return r.json()["access_token"]

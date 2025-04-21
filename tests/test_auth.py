from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
def test_token():
    r=client.post("/api/v1/auth/token",data={"username":"user@example.com","password":"password"});assert r.status_code==200;assert"access_token"in r.json()

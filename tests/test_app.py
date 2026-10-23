
from fastapi.testclient import TestClient
from app.main import app


def test_root():
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.json()["message"] == ( "Food Delivery API running")
    assert response.json()["level"] == 15

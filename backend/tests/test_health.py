from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok_status_and_stable_service_identifier() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "weview-work4-api",
    }

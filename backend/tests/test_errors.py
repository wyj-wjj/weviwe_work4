from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import AppError, register_exception_handlers
from app.main import app


def test_unknown_routes_return_consistent_json_error_without_stack_trace() -> None:
    client = TestClient(app)

    response = client.get("/missing")

    assert response.status_code == 404
    payload = response.json()
    assert payload == {
        "error": {
            "code": "not_found",
            "message": "Resource not found.",
            "details": None,
        }
    }
    assert "Traceback" not in response.text
    assert "stack" not in response.text.lower()


def test_controlled_application_errors_return_consistent_json_without_stack_trace() -> None:
    controlled_app = FastAPI()
    register_exception_handlers(controlled_app)

    @controlled_app.get("/controlled-error")
    def controlled_error() -> None:
        raise AppError(
            code="example_error",
            message="Controlled failure.",
            status_code=409,
            details={"field": "title"},
        )

    client = TestClient(controlled_app)

    response = client.get("/controlled-error")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "example_error",
            "message": "Controlled failure.",
            "details": {"field": "title"},
        }
    }
    assert "Traceback" not in response.text
    assert "stack" not in response.text.lower()

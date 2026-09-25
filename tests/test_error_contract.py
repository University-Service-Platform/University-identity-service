from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_exception_handlers
from app.core.logging import REQUEST_ID_HEADER, register_request_logging
from tests.helpers import auth_header, create_user


def assert_error_envelope(body: dict, code: str):
    assert body["success"] is False
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    assert body["timestamp"].endswith("Z")


def test_service_error_keeps_code_and_adds_timestamp(client, db_session):
    create_user(db_session, "usr-admin-err-01", role="ADMIN")
    response = client.get("/validation/users/usr-does-not-exist", headers=auth_header("usr-admin-err-01"))
    assert response.status_code == 404
    assert_error_envelope(response.json(), "USER_NOT_FOUND")


def test_missing_token_returns_401_envelope_with_www_authenticate(client):
    response = client.get("/protected/user-status")
    assert response.status_code == 401
    assert_error_envelope(response.json(), "UNAUTHORIZED")
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_request_validation_error_uses_standard_envelope(client, db_session):
    create_user(db_session, "usr-admin-err-02", role="ADMIN")
    response = client.post(
        "/users",
        json={"university_id": "STU900", "name": "Invalid Email", "email": "not-an-email", "account_type": "STUDENT"},
        headers=auth_header("usr-admin-err-02"),
    )
    assert response.status_code == 422
    body = response.json()
    assert_error_envelope(body, "VALIDATION_ERROR")
    fields = [d["field"] for d in body["error"]["details"]]
    assert "body.email" in fields


def test_unknown_route_returns_404_envelope(client):
    response = client.get("/no-such-endpoint")
    assert response.status_code == 404
    assert_error_envelope(response.json(), "NOT_FOUND")


def test_method_not_allowed_returns_405_envelope(client):
    response = client.post("/health")
    assert response.status_code == 405
    assert_error_envelope(response.json(), "METHOD_NOT_ALLOWED")


def test_unhandled_exception_returns_safe_500():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("database password is hunter2")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert_error_envelope(body, "INTERNAL_SERVER_ERROR")
    assert "hunter2" not in response.text


def test_request_id_is_propagated_or_generated():
    app = FastAPI()
    register_request_logging(app)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    test_client = TestClient(app)
    echoed = test_client.get("/ping", headers={REQUEST_ID_HEADER: "gateway-trace-123"})
    assert echoed.headers[REQUEST_ID_HEADER] == "gateway-trace-123"

    generated = test_client.get("/ping")
    assert len(generated.headers[REQUEST_ID_HEADER]) == 32

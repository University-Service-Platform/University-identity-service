"""
CORS for browser clients calling the service directly, and ROOT_PATH for running behind
the API Gateway with a stripped prefix (e.g. /identity).
"""
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import _env_list, get_settings
from app.core.cors import register_cors
from app.main import app
from tests.helpers import auth_header, create_user

FRONTEND = "http://localhost:5173"


def cors_app(origins):
    test_app = FastAPI()
    register_cors(test_app, origins)

    @test_app.get("/ping")
    def ping():
        return {"ok": True}

    return test_app


# ---------------------------------------------------------------- settings

def test_cors_origins_are_parsed_from_a_comma_separated_list(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", " http://localhost:5173, ,https://portal.university.example ")
    assert _env_list("CORS_ALLOWED_ORIGINS") == ("http://localhost:5173", "https://portal.university.example")


def test_cors_and_root_path_are_off_by_default():
    settings = get_settings()
    assert settings.cors_allowed_origins == ()
    assert settings.root_path == ""


def test_wildcard_cors_origin_is_rejected_in_production():
    production = replace(get_settings(), environment="production", jwt_algorithm="RS256",
                         jwt_private_key_path="k.pem", jwt_public_key_path="p.pem",
                         cors_allowed_origins=("*",))
    with pytest.raises(RuntimeError, match="CORS_ALLOWED_ORIGINS"):
        production.validate()


def test_wildcard_cors_origin_is_allowed_in_development():
    replace(get_settings(), cors_allowed_origins=("*",)).validate()


@pytest.mark.parametrize("root_path", ["identity", "/identity/"])
def test_malformed_root_path_is_rejected(root_path):
    with pytest.raises(RuntimeError, match="ROOT_PATH"):
        replace(get_settings(), root_path=root_path).validate()


# ---------------------------------------------------------------- CORS behaviour

def test_no_cors_headers_when_no_origins_are_configured(client):
    response = client.get("/health", headers={"Origin": FRONTEND})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_preflight_from_an_allowed_origin_succeeds():
    response = TestClient(cors_app([FRONTEND])).options("/ping", headers={
        "Origin": FRONTEND,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization, X-Request-ID",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers and "x-request-id" in allowed_headers
    # Bearer tokens, not cookies: credentials are never allowed
    assert "access-control-allow-credentials" not in response.headers


def test_simple_request_from_an_allowed_origin_exposes_tracing_headers():
    response = TestClient(cors_app([FRONTEND])).get("/ping", headers={"Origin": FRONTEND})
    assert response.headers["access-control-allow-origin"] == FRONTEND
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "x-request-id" in exposed and "deprecation" in exposed and "link" in exposed


def test_other_origins_are_not_allowed():
    response = TestClient(cors_app([FRONTEND])).options("/ping", headers={
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "GET",
    })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_error_responses_carry_cors_headers_on_the_real_app(client):
    """CORS is outermost, so a browser can read our error envelope (e.g. 401) too."""
    cors_enabled = FastAPI()
    cors_enabled.mount("/", app)
    register_cors(cors_enabled, [FRONTEND])
    with TestClient(cors_enabled) as browser:
        response = browser.get("/api/v1/auth/me", headers={"Origin": FRONTEND})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["access-control-allow-origin"] == FRONTEND


# ---------------------------------------------------------------- behind the gateway

@pytest.fixture
def gateway_client(client):
    """The gateway forwards /identity/api/v1/... as /api/v1/... and uvicorn reports root_path=/identity."""
    return TestClient(app, root_path="/identity")


def test_swagger_ui_loads_openapi_through_the_gateway_prefix(gateway_client):
    html = gateway_client.get("/docs").text
    assert "/identity/openapi.json" in html


def test_openapi_advertises_the_gateway_prefix_as_server(gateway_client):
    servers = gateway_client.get("/openapi.json").json().get("servers", [])
    assert {"url": "/identity"} in servers


def test_routes_still_match_behind_the_gateway(gateway_client):
    assert gateway_client.get("/health").status_code == 200
    assert gateway_client.get("/api/v1/auth/me").json()["error"]["code"] == "UNAUTHORIZED"


def test_legacy_successor_link_includes_the_gateway_prefix(gateway_client, db_session):
    create_user(db_session, "usr-gateway-1")
    response = gateway_client.get("/validation/users/usr-gateway-1")
    assert response.status_code == 200
    assert response.headers["link"] == '</identity/api/v1/validation/users/usr-gateway-1>; rel="successor-version"'


def test_explicit_legacy_successor_includes_the_gateway_prefix(gateway_client, db_session):
    create_user(db_session, "usr-gateway-2")
    response = gateway_client.get("/protected/user-status", headers=auth_header("usr-gateway-2"))
    assert response.headers["link"] == '</identity/api/v1/auth/me>; rel="successor-version"'


def test_legacy_successor_link_without_gateway(client, db_session):
    create_user(db_session, "usr-gateway-3")
    response = client.get("/validation/users/usr-gateway-3")
    assert response.headers["link"] == '</api/v1/validation/users/usr-gateway-3>; rel="successor-version"'

"""
End-to-end workflows against a database built exactly as in deployment:
Alembic migrations + `app.seed` reference data + synthetic demo users.
Only the Directory Service is stubbed (httpx.MockTransport).
"""
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.database import get_db
from app.integrations.directory_client import DirectoryClient, get_directory_client
from app.main import app
from app.reference_data import ensure_reference_data
from app.seed import seed_demo_users

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PASSWORD = "Demo-Passw0rd!"


@pytest.fixture
def deployed_client(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 'e2e.db').as_posix()}"
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine, autoflush=False)
    with Session() as session:
        ensure_reference_data(session)
        seed_demo_users(session, DEMO_PASSWORD)

    def _db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def login(client, username, password=DEMO_PASSWORD):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_account_lifecycle_from_creation_to_deactivation(deployed_client):
    client = deployed_client
    admin = login(client, "ADM001")

    # Administrator creates a synthetic staff account with a password
    created = client.post("/api/v1/users", headers=admin, json={
        "university_id": "STF900", "name": "New Resource Manager",
        "email": "stf900@university.example", "account_type": "STAFF", "password": "Initial-Pass-900",
    })
    assert created.status_code == 201
    user_id = created.json()["data"]["id"]

    # ... assigns a platform role
    assert client.post(f"/api/v1/users/{user_id}/roles", headers=admin,
                       json={"role_name": "RESOURCE_MANAGER"}).status_code == 200

    # The user logs in and sees a role-relevant identity for navigation
    user = login(client, "STF900", "Initial-Pass-900")
    me = client.get("/api/v1/auth/me", headers=user).json()["data"]
    assert me["roles"] == ["RESOURCE_MANAGER"]
    assert me["permissions"] == ["profile:read_own"]

    # Another service validates the user with a forwarded token
    validated = client.get(f"/api/v1/validation/users/{user_id}",
                           params={"required_role": "RESOURCE_MANAGER"}, headers=user).json()["data"]
    assert validated["is_valid"] is True and validated["is_authorized"] is True

    # Administrator deactivates the account: access stops immediately
    assert client.patch(f"/api/v1/users/{user_id}/status", headers=admin,
                        json={"status": "INACTIVE"}).status_code == 200
    assert client.get("/api/v1/auth/me", headers=user).status_code == 403
    assert client.post("/api/v1/auth/login",
                       json={"username": "STF900", "password": "Initial-Pass-900"}).status_code == 403
    assert client.get(f"/api/v1/validation/users/{user_id}", params={"require_active": "true"},
                      headers=admin).status_code == 403

    # Every administrative step is traceable
    actions = [e["action"] for e in client.get("/api/v1/audit-logs", params={"target_id": user_id},
                                               headers=admin).json()["data"]]
    assert actions == ["USER_STATUS_CHANGED", "LOGIN_SUCCEEDED", "ROLE_ASSIGNED", "USER_CREATED"]


def test_seeded_platform_roles_can_log_in(deployed_client):
    for university_id, role in [("STU001", "STUDENT"), ("ACD001", "ACADEMIC_STAFF"),
                                ("SDO001", "SERVICE_DESK_OFFICER"), ("TEC001", "TECHNICIAN"),
                                ("RMG001", "RESOURCE_MANAGER"), ("EVO001", "EVENT_ORGANIZER")]:
        me = deployed_client.get("/api/v1/auth/me", headers=login(deployed_client, university_id)).json()["data"]
        assert me["roles"] == [role]


def test_seeded_inactive_demo_user_cannot_log_in(deployed_client):
    response = deployed_client.post("/api/v1/auth/login",
                                    json={"username": "STU002", "password": DEMO_PASSWORD})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_INACTIVE"


def test_gateway_can_verify_tokens_using_only_the_published_jwks(deployed_client):
    """Simulates the API Gateway: it knows the JWKS URL, issuer and audience, nothing else."""
    token = login(deployed_client, "RMG001")["Authorization"].split()[1]
    jwks = deployed_client.get("/.well-known/jwks.json").json()
    key = next(k for k in jwks["keys"] if k["kid"] == jwt.get_unverified_header(token)["kid"])

    claims = jwt.decode(token, key, algorithms=["RS256"],
                        audience=get_settings().jwt_audience, issuer=get_settings().jwt_issuer)
    assert claims["sub"] == "usr-resourcemgr-001"
    assert claims["roles"] == ["RESOURCE_MANAGER"]


def test_identity_and_directory_workflow(deployed_client):
    """Identity (roles) + Directory (responsibility) decide eligibility together."""
    seen = []

    def directory(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"success": True, "data": {
            "user_id": "usr-servicedesk-001", "is_valid": True,
            "responsibilities": [{"responsibility_id": "rsp-1", "user_id": "usr-servicedesk-001",
                                  "service_unit_id": "su-it", "service_unit_name": "IT Services",
                                  "role_title": "Service Desk Lead", "status": "ACTIVE"}],
        }})

    app.dependency_overrides[get_directory_client] = lambda: DirectoryClient(
        "http://directory.test", 1.0, transport=httpx.MockTransport(directory))

    officer = login(deployed_client, "SDO001")
    data = deployed_client.get("/api/v1/validation/users/SDO001/eligibility", headers=officer, params={
        "required_role": "SERVICE_DESK_OFFICER", "relationship": "RESPONSIBILITY", "service_unit_id": "su-it",
    }).json()["data"]
    assert data["eligible"] is True
    assert seen[0].url.path == "/validation/users/usr-servicedesk-001/responsibilities"

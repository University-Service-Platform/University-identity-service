"""The shared demo accounts can't be changed through the API while PROTECT_DEMO_USERS is on."""
from dataclasses import replace

import pytest

from app import demo_accounts
from app.core.config import get_settings
from app.models.user import User
from app.reference_data import ensure_reference_data
from app.seed import seed_demo_users
from tests.helpers import auth_header, create_user

PASSWORD = "Demo-Pass-123"


@pytest.fixture
def demo(db_session):
    ensure_reference_data(db_session)
    seed_demo_users(db_session, PASSWORD)
    return db_session


@pytest.mark.parametrize("method,path,body", [
    ("PUT", "/api/v1/users/usr-student-001", {"name": "Hacked"}),
    ("PATCH", "/api/v1/users/usr-student-001/status", {"status": "INACTIVE"}),
    ("DELETE", "/api/v1/users/usr-student-001", None),
    ("DELETE", "/api/v1/users/STU001", None),                     # by university ID too
    ("PUT", "/api/v1/users/usr-student-001/password", {"new_password": "Other-Pass-123"}),
    ("POST", "/api/v1/users/usr-student-001/roles", {"role_name": "ADMIN"}),
    ("PUT", "/api/v1/users/usr-admin-001/roles", {"old_role_name": "ADMIN", "new_role_name": "STUDENT"}),
    ("DELETE", "/api/v1/users/usr-student-001/roles/STUDENT", None),
])
def test_admin_cannot_change_demo_accounts(client, demo, method, path, body):
    response = client.request(method, path, headers=auth_header("usr-admin-001"), json=body)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "DEMO_ACCOUNT_PROTECTED"
    student = demo.query(User).filter(User.id == "usr-student-001").one()
    assert student.name == "Demo Student" and student.status.value == "ACTIVE"


def test_demo_user_cannot_change_own_password_or_name(client, demo):
    headers = auth_header("usr-student-001")
    response = client.post("/api/v1/auth/change-password", headers=headers,
                           json={"current_password": PASSWORD, "new_password": "Other-Pass-123"})
    assert response.json()["error"]["code"] == "DEMO_ACCOUNT_PROTECTED"
    response = client.put("/api/v1/users/profile", headers=headers, json={"firstName": "X", "lastName": "Y"})
    assert response.json()["error"]["code"] == "DEMO_ACCOUNT_PROTECTED"
    # Reading is unaffected, and the password still works
    assert client.get("/api/v1/users/profile", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/login", json={"username": "STU001", "password": PASSWORD}).status_code == 200


def test_other_accounts_can_still_be_managed(client, demo):
    create_user(demo, "usr-own-test", role="STUDENT")
    admin = auth_header("usr-admin-001")
    assert client.put("/api/v1/users/usr-own-test", headers=admin, json={"name": "Renamed"}).status_code == 200
    assert client.post("/api/v1/users/usr-own-test/roles", headers=admin,
                       json={"role_name": "TECHNICIAN"}).status_code == 200
    assert client.delete("/api/v1/users/usr-own-test", headers=admin).status_code == 200


def test_protection_can_be_switched_off(client, demo, monkeypatch):
    monkeypatch.setattr(demo_accounts, "get_settings", lambda: replace(get_settings(), protect_demo_users=False))
    response = client.put("/api/v1/users/usr-student-001", headers=auth_header("usr-admin-001"),
                          json={"name": "Renamed Demo"})
    assert response.status_code == 200


def test_setting_defaults_on_and_reads_the_environment(monkeypatch):
    get_settings.cache_clear()
    try:
        assert get_settings().protect_demo_users is True
        monkeypatch.setenv("PROTECT_DEMO_USERS", "false")
        get_settings.cache_clear()
        assert get_settings().protect_demo_users is False
    finally:
        monkeypatch.delenv("PROTECT_DEMO_USERS", raising=False)
        get_settings.cache_clear()


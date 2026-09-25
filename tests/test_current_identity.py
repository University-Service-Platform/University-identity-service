import pytest

from app.models.role import Role, UserRole
from app.models.user import AccountStatus
from app.reference_data import ROLE_PERMISSIONS, ensure_reference_data
from tests.helpers import auth_header, create_user


@pytest.fixture
def reference_data(db_session):
    ensure_reference_data(db_session)
    return db_session


def test_me_returns_identity_roles_and_permissions(client, reference_data):
    user = create_user(reference_data, "usr-me-01", role="RESOURCE_MANAGER")

    response = client.get("/api/v1/auth/me", headers=auth_header(user.id))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user_id"] == user.id
    assert data["university_id"] == user.university_id
    assert data["status"] == "ACTIVE"
    assert data["roles"] == ["RESOURCE_MANAGER"]
    assert data["primary_role"] == "RESOURCE_MANAGER"
    assert data["permissions"] == sorted(ROLE_PERMISSIONS["RESOURCE_MANAGER"])


def test_me_for_admin_lists_all_identity_permissions(client, reference_data):
    create_user(reference_data, "usr-me-02", role="ADMIN")
    data = client.get("/api/v1/auth/me", headers=auth_header("usr-me-02")).json()["data"]
    assert data["permissions"] == sorted(ROLE_PERMISSIONS["ADMIN"])


def test_me_reflects_role_changes_immediately(client, reference_data):
    user = create_user(reference_data, "usr-me-03", role="STUDENT")
    event_organizer = reference_data.query(Role).filter_by(name="EVENT_ORGANIZER").one()
    reference_data.add(UserRole(user_id=user.id, role_id=event_organizer.id))
    reference_data.commit()

    data = client.get("/api/v1/auth/me", headers=auth_header(user.id)).json()["data"]
    assert set(data["roles"]) == {"STUDENT", "EVENT_ORGANIZER"}


def test_me_rejects_inactive_account(client, reference_data):
    create_user(reference_data, "usr-me-04", role="STUDENT", status=AccountStatus.INACTIVE)
    response = client.get("/api/v1/auth/me", headers=auth_header("usr-me-04"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_INACTIVE"


def test_me_requires_authentication(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"

import pytest

from app.models.user import AccountStatus
from app.reference_data import ensure_reference_data
from tests.helpers import auth_header, create_user


@pytest.fixture
def admin(db_session):
    ensure_reference_data(db_session)
    return create_user(db_session, "usr-version-admin", role="ADMIN")


def test_v1_and_legacy_routes_return_the_same_data(client, db_session, admin):
    headers = auth_header(admin.id)
    legacy = client.get("/users", headers=headers)
    v1 = client.get("/api/v1/users", headers=headers)
    assert legacy.status_code == v1.status_code == 200
    assert legacy.json() == v1.json()


def test_legacy_routes_announce_deprecation_and_successor(client, db_session, admin):
    response = client.get(f"/users/{admin.id}/role", headers=auth_header(admin.id))
    assert response.status_code == 200
    assert response.headers["Deprecation"] == "true"
    assert response.headers["Link"] == f'</api/v1/users/{admin.id}/role>; rel="successor-version"'


def test_v1_routes_are_not_marked_deprecated(client, db_session, admin):
    response = client.get(f"/api/v1/users/{admin.id}/role", headers=auth_header(admin.id))
    assert response.status_code == 200
    assert "Deprecation" not in response.headers


def test_protected_demo_routes_point_to_auth_me(client, db_session, admin):
    response = client.get("/protected/user-status", headers=auth_header(admin.id))
    assert response.status_code == 200
    assert response.headers["Link"] == '</api/v1/auth/me>; rel="successor-version"'
    assert client.get("/api/v1/protected/user-status", headers=auth_header(admin.id)).status_code == 404


def test_health_stays_unversioned(client):
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 404


# ---------------------------------------------------------------- validation contract

def test_v1_validation_requires_bearer_token(client, db_session, admin):
    response = client.get(f"/api/v1/validation/users/{admin.id}")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_v1_validation_omits_email_but_legacy_keeps_it(client, db_session, admin):
    student = create_user(db_session, "usr-version-student", role="STUDENT")

    v1 = client.get(f"/api/v1/validation/users/{student.university_id}", headers=auth_header(admin.id))
    assert v1.status_code == 200
    data = v1.json()["data"]
    assert data["user_id"] == student.id
    assert data["is_valid"] is True
    assert data["roles"] == ["STUDENT"]
    assert "email" not in data

    legacy = client.get(f"/validation/users/{student.id}")
    assert legacy.status_code == 200
    assert legacy.json()["data"]["email"] == student.email


def test_v1_validation_role_check_and_error_cases(client, db_session, admin):
    create_user(db_session, "usr-version-tech", role="TECHNICIAN")
    create_user(db_session, "usr-version-inactive", role="STUDENT", status=AccountStatus.INACTIVE)
    headers = auth_header(admin.id)

    role_check = client.get("/api/v1/validation/users/usr-version-tech",
                            params={"required_role": "resource_manager"}, headers=headers).json()["data"]
    assert role_check["is_authorized"] is False
    assert role_check["required_role_checked"] == "RESOURCE_MANAGER"

    inactive = client.get("/api/v1/validation/users/usr-version-inactive",
                          params={"require_active": "true"}, headers=headers)
    assert inactive.status_code == 403
    assert inactive.json()["error"]["code"] == "ACCOUNT_INACTIVE"

    unknown = client.get("/api/v1/validation/users/usr-nobody", headers=headers)
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "USER_NOT_FOUND"


def test_openapi_marks_every_legacy_operation_deprecated(client):
    paths = client.get("/openapi.json").json()["paths"]
    for path, operations in paths.items():
        for operation in operations.values():
            is_legacy = not (path.startswith("/api/v1/") or path in ("/health", "/.well-known/jwks.json"))
            assert operation.get("deprecated", False) is is_legacy, path

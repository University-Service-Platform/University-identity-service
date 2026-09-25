import pytest

from app.models.permission import Permission, RolePermission
from app.models.role import Role
from app.reference_data import PERMISSIONS, ROLE_PERMISSIONS, ROLES, ensure_reference_data
from tests.helpers import auth_header, create_user


@pytest.fixture
def reference_data(db_session):
    ensure_reference_data(db_session)
    return db_session


def test_reference_data_is_created_once(reference_data):
    ensure_reference_data(reference_data)  # second run must not duplicate anything

    assert reference_data.query(Role).count() == len(ROLES)
    assert reference_data.query(Permission).count() == len(PERMISSIONS)
    expected_grants = sum(len(codes) for codes in ROLE_PERMISSIONS.values())
    assert reference_data.query(RolePermission).count() == expected_grants


def test_platform_defines_at_least_four_role_types(reference_data):
    names = {role.name for role in reference_data.query(Role).all()}
    assert len(names) >= 4
    assert {"ADMIN", "STUDENT", "RESOURCE_MANAGER", "SERVICE_DESK_OFFICER", "TECHNICIAN"} <= names


def test_staff_can_list_role_catalogue_with_permissions(client, reference_data):
    create_user(reference_data, "usr-staff-cat-01", role="STAFF")

    response = client.get("/api/v1/roles", headers=auth_header("usr-staff-cat-01"))
    assert response.status_code == 200
    roles = {entry["name"]: entry for entry in response.json()["data"]}
    assert set(roles) == {name for name, _ in ROLES}
    assert "roles:assign" in roles["ADMIN"]["permissions"]
    assert roles["STUDENT"]["permissions"] == ["profile:read_own"]


def test_get_single_role_is_case_insensitive(client, reference_data):
    create_user(reference_data, "usr-admin-cat-02", role="ADMIN")

    response = client.get("/api/v1/roles/resource_manager", headers=auth_header("usr-admin-cat-02"))
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "RESOURCE_MANAGER"


def test_unknown_role_returns_404(client, reference_data):
    create_user(reference_data, "usr-admin-cat-03", role="ADMIN")

    response = client.get("/api/v1/roles/NOT_A_ROLE", headers=auth_header("usr-admin-cat-03"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ROLE_NOT_FOUND"


def test_student_without_roles_read_permission_is_forbidden(client, reference_data):
    create_user(reference_data, "usr-student-cat-04", role="STUDENT")

    response = client.get("/api/v1/roles", headers=auth_header("usr-student-cat-04"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_role_catalogue_requires_authentication(client, reference_data):
    response = client.get("/api/v1/roles")
    assert response.status_code == 401


@pytest.mark.parametrize("role_name", [name for name, _ in ROLES])
def test_users_read_permission_matches_enforced_role_rule(client, reference_data, role_name):
    """The permission catalogue must describe what the role-based endpoints actually allow."""
    user_id = f"usr-consistency-{role_name.lower().replace('_', '-')}"
    create_user(reference_data, user_id, role=role_name)

    response = client.get("/users", headers=auth_header(user_id))
    expected = 200 if "users:read" in ROLE_PERMISSIONS[role_name] else 403
    assert response.status_code == expected

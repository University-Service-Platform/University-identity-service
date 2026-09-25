import pytest

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.reference_data import ensure_reference_data
from tests.helpers import auth_header, create_user

ADMIN_ID = "usr-audit-admin"


@pytest.fixture
def admin(db_session):
    ensure_reference_data(db_session)
    return create_user(db_session, ADMIN_ID, role="ADMIN")


def audit_actions(db, target_id=None):
    query = db.query(AuditLog)
    if target_id:
        query = query.filter(AuditLog.target_id == target_id)
    return [row.action for row in query.order_by(AuditLog.id).all()]


def test_user_lifecycle_is_audited(client, db_session, admin):
    headers = auth_header(ADMIN_ID)
    created = client.post(
        "/users",
        json={"university_id": "STU501", "name": "Audit Student", "email": "stu501@university.example",
              "account_type": "STUDENT"},
        headers=headers,
    ).json()["data"]
    user_id = created["id"]

    client.put(f"/users/{user_id}", json={"name": "Renamed Student"}, headers=headers)
    client.patch(f"/users/{user_id}/status", json={"status": "INACTIVE"}, headers=headers)
    client.delete(f"/users/{user_id}", headers=headers)

    assert audit_actions(db_session, user_id) == [
        "USER_CREATED", "USER_UPDATED", "USER_STATUS_CHANGED", "USER_DELETED"
    ]
    status_entry = db_session.query(AuditLog).filter_by(action="USER_STATUS_CHANGED").one()
    assert status_entry.actor_user_id == ADMIN_ID
    assert '"status": "INACTIVE"' in status_entry.details


def test_role_changes_are_audited(client, db_session, admin):
    target = create_user(db_session, "usr-audit-role", role="STUDENT")
    headers = auth_header(ADMIN_ID)

    client.post(f"/users/{target.id}/roles", json={"role_name": "technician"}, headers=headers)
    client.put(f"/users/{target.id}/roles", json={"old_role_name": "TECHNICIAN", "new_role_name": "RESOURCE_MANAGER"},
               headers=headers)
    client.delete(f"/users/{target.id}/roles/RESOURCE_MANAGER", headers=headers)

    assert audit_actions(db_session, target.id) == ["ROLE_ASSIGNED", "ROLE_UPDATED", "ROLE_REVOKED"]


def test_failed_actions_are_not_audited(client, db_session, admin):
    response = client.patch("/users/usr-does-not-exist/status", json={"status": "INACTIVE"},
                            headers=auth_header(ADMIN_ID))
    assert response.status_code == 404
    assert audit_actions(db_session) == []


def test_login_and_password_events_are_audited(client, db_session, admin):
    user = create_user(db_session, "usr-audit-login", role="STUDENT")
    user.password_hash = hash_password("Initial-Pass-1")
    db_session.commit()

    client.post("/api/v1/auth/login", json={"username": user.university_id, "password": "Initial-Pass-1"})
    client.put(f"/api/v1/users/{user.id}/password", json={"new_password": "Reset-Pass-2"},
               headers=auth_header(ADMIN_ID))
    client.post("/api/v1/auth/change-password",
                json={"current_password": "Reset-Pass-2", "new_password": "Changed-Pass-3"},
                headers=auth_header(user.id))

    assert audit_actions(db_session, user.id) == ["LOGIN_SUCCEEDED", "PASSWORD_SET", "PASSWORD_CHANGED"]
    assert "Pass" not in "".join(row.details or "" for row in db_session.query(AuditLog).all())


def test_admin_can_read_and_filter_audit_log(client, db_session, admin):
    target = create_user(db_session, "usr-audit-read", role="STUDENT")
    headers = auth_header(ADMIN_ID)
    client.patch(f"/users/{target.id}/status", json={"status": "INACTIVE"}, headers=headers)
    client.patch(f"/users/{target.id}/status", json={"status": "ACTIVE"}, headers=headers)

    response = client.get("/api/v1/audit-logs", params={"target_id": target.id}, headers=headers)
    assert response.status_code == 200
    entries = response.json()["data"]
    assert [e["details"]["status"] for e in entries] == ["ACTIVE", "INACTIVE"]  # newest first

    filtered = client.get("/api/v1/audit-logs", params={"action": "user_created"}, headers=headers).json()["data"]
    assert filtered == []


def test_audit_log_requires_audit_permission(client, db_session, admin):
    create_user(db_session, "usr-audit-staff", role="STAFF")
    response = client.get("/api/v1/audit-logs", headers=auth_header("usr-audit-staff"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

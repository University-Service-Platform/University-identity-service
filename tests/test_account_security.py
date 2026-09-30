"""Sign-in lockout, sessions ending on a password change, and keeping an administrator."""
from datetime import timedelta

import pytest

from app.core.security import hash_password
from app.core.time import utc_now
from app.models.audit_log import AuditLog
from app.models.user import AccountStatus
from app.reference_data import ensure_reference_data
from app.services.credentials import MAX_FAILED_LOGINS
from tests.helpers import auth_header, create_user

PASSWORD = "Right-Pass-123"


def with_password(db, user):
    user.password_hash = hash_password(PASSWORD)
    db.commit()
    return user


def login(client, username, password):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


# ---------------------------------------------------------------- lockout

@pytest.fixture
def account(db_session):
    return with_password(db_session, create_user(db_session, "usr-lock-01", role="STUDENT"))


def test_account_locks_after_repeated_wrong_passwords(client, db_session, account):
    for _ in range(MAX_FAILED_LOGINS - 1):
        assert login(client, account.university_id, "wrong").status_code == 401
    locked = login(client, account.university_id, "wrong")
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "ACCOUNT_LOCKED"
    # Even the right password is refused while locked
    assert login(client, account.university_id, PASSWORD).status_code == 429
    assert db_session.query(AuditLog).filter(AuditLog.action == "ACCOUNT_LOCKED").count() == 1


def test_lock_expires(client, db_session, account):
    for _ in range(MAX_FAILED_LOGINS):
        login(client, account.university_id, "wrong")
    account.locked_until = utc_now() - timedelta(seconds=1)
    db_session.commit()
    assert login(client, account.university_id, PASSWORD).status_code == 200


def test_a_successful_login_resets_the_count(client, db_session, account):
    for _ in range(MAX_FAILED_LOGINS - 1):
        login(client, account.university_id, "wrong")
    assert login(client, account.university_id, PASSWORD).status_code == 200
    for _ in range(MAX_FAILED_LOGINS - 1):
        assert login(client, account.university_id, "wrong").status_code == 401
    assert login(client, account.university_id, PASSWORD).status_code == 200


def test_an_administrator_setting_the_password_unlocks(client, db_session, account):
    ensure_reference_data(db_session)   # ADMIN's users:manage permission
    admin = create_user(db_session, "usr-lock-admin", role="ADMIN")
    for _ in range(MAX_FAILED_LOGINS):
        login(client, account.university_id, "wrong")
    assert client.put(f"/api/v1/users/{account.id}/password", headers=auth_header(admin.id),
                      json={"new_password": "Fresh-Pass-456"}).status_code == 200
    assert login(client, account.university_id, "Fresh-Pass-456").status_code == 200


def test_shared_demo_accounts_never_lock(client, db_session):
    demo = with_password(db_session, create_user(db_session, "usr-student-001", role="STUDENT"))
    for _ in range(MAX_FAILED_LOGINS + 2):
        assert login(client, demo.university_id, "wrong").status_code == 401
    assert login(client, demo.university_id, PASSWORD).status_code == 200


# ---------------------------------------------------------------- sessions end on a password change

def test_tokens_from_before_a_password_change_are_refused(client, db_session, account):
    token = login(client, account.university_id, PASSWORD).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    # The change happens after the token was issued (a second later than its iat)
    account.password_changed_at = (utc_now() + timedelta(seconds=2)).replace(microsecond=0)
    db_session.commit()

    refused = client.get("/api/v1/auth/me", headers=headers)
    assert refused.status_code == 401 and refused.json()["error"]["code"] == "SESSION_EXPIRED"


def test_changing_the_password_records_when(client, db_session, account):
    token = login(client, account.university_id, PASSWORD).json()["data"]["access_token"]
    response = client.post("/api/v1/auth/change-password", headers={"Authorization": f"Bearer {token}"},
                           json={"current_password": PASSWORD, "new_password": "Fresh-Pass-456"})
    assert response.status_code == 200
    db_session.refresh(account)
    assert account.password_changed_at is not None
    # A new sign-in works straight away
    new_token = login(client, account.university_id, "Fresh-Pass-456").json()["data"]["access_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"}).status_code == 200


# ---------------------------------------------------------------- administrators

def test_admin_cannot_delete_or_deactivate_themselves(client, db_session):
    admin = create_user(db_session, "usr-adm-a", role="ADMIN")
    create_user(db_session, "usr-adm-b", role="ADMIN")
    headers = auth_header(admin.id)
    for response in (client.delete(f"/api/v1/users/{admin.id}", headers=headers),
                     client.delete(f"/api/v1/users/{admin.university_id}", headers=headers),
                     client.patch(f"/api/v1/users/{admin.id}/status", headers=headers, json={"status": "INACTIVE"})):
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CANNOT_CHANGE_OWN_ACCOUNT"


def test_the_last_admin_cannot_be_removed(client, db_session):
    admin = create_user(db_session, "usr-adm-a", role="ADMIN")
    other = create_user(db_session, "usr-adm-b", role="ADMIN")
    headers = auth_header(admin.id)

    # Two admins: one can be demoted
    assert client.delete(f"/api/v1/users/{other.id}/roles/ADMIN", headers=headers).status_code == 200
    # Now the remaining one can't be, either way
    for response in (client.delete(f"/api/v1/users/{admin.id}/roles/ADMIN", headers=headers),
                     client.put(f"/api/v1/users/{admin.id}/roles", headers=headers,
                                json={"old_role_name": "ADMIN", "new_role_name": "STUDENT"})):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "LAST_ADMIN"


def test_inactive_admins_do_not_count(client, db_session):
    admin = create_user(db_session, "usr-adm-a", role="ADMIN")
    create_user(db_session, "usr-adm-b", role="ADMIN", status=AccountStatus.INACTIVE)
    response = client.delete(f"/api/v1/users/{admin.id}/roles/ADMIN", headers=auth_header(admin.id))
    assert response.status_code == 409


def test_other_accounts_are_unaffected(client, db_session):
    admin = create_user(db_session, "usr-adm-a", role="ADMIN")
    student = create_user(db_session, "usr-plain", role="STUDENT")
    headers = auth_header(admin.id)
    assert client.patch(f"/api/v1/users/{student.id}/status", headers=headers, json={"status": "INACTIVE"}).status_code == 200
    assert client.delete(f"/api/v1/users/{student.id}", headers=headers).status_code == 200

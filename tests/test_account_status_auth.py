import pytest
from app.models.user import User, AccountType, AccountStatus
from app.dependencies.auth import create_access_token

def seed_auth_users(db_session):
    active_user = User(
        id="usr-active-101",
        university_id="STU101",
        name="Active Student",
        email="active101@kln.ac.lk",
        account_type=AccountType.STUDENT,
        status=AccountStatus.ACTIVE
    )
    inactive_user = User(
        id="usr-inactive-102",
        university_id="STU102",
        name="Inactive Student",
        email="inactive102@kln.ac.lk",
        account_type=AccountType.STUDENT,
        status=AccountStatus.INACTIVE
    )
    db_session.add_all([active_user, inactive_user])
    db_session.commit()

def test_active_account_access(client, db_session):
    seed_auth_users(db_session)
    token = create_access_token({"sub": "usr-active-101"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/protected/user-status", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ACTIVE"
    assert data["data"]["user_id"] == "usr-active-101"

def test_inactive_account_denied(client, db_session):
    seed_auth_users(db_session)
    token = create_access_token({"sub": "usr-inactive-102"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/protected/user-status", headers=headers)
    assert response.status_code == 403
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "ACCOUNT_INACTIVE"

def test_missing_authentication(client):
    response = client.get("/protected/user-status")
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"

def test_invalid_token(client):
    headers = {"Authorization": "Bearer invalid.jwt.token"}
    response = client.get("/protected/user-status", headers=headers)
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_TOKEN"

def test_deactivation_integration_flow(client, db_session):
    """
    Integration test:
    1. Active user succeeds.
    2. Account status updated to INACTIVE (simulating Pavithira's deactivation endpoint).
    3. Immediate authorization check on next request fails with 403.
    """
    seed_auth_users(db_session)
    token = create_access_token({"sub": "usr-active-101"})
    headers = {"Authorization": f"Bearer {token}"}

    # First request: ACTIVE -> 200 OK
    res1 = client.get("/protected/user-status", headers=headers)
    assert res1.status_code == 200

    # Simulate account deactivation action
    user = db_session.query(User).filter(User.id == "usr-active-101").first()
    user.status = AccountStatus.INACTIVE
    db_session.commit()

    # Second request: now INACTIVE -> 403 Forbidden
    res2 = client.get("/protected/user-status", headers=headers)
    assert res2.status_code == 403
    assert res2.json()["error"]["code"] == "ACCOUNT_INACTIVE"

def test_reactivation_integration_flow(client, db_session):
    """
    Integration test:
    1. Inactive user fails with 403.
    2. Account status updated to ACTIVE (simulating Pavithira's activation endpoint).
    3. Subsequent request succeeds with 200 OK.
    """
    seed_auth_users(db_session)
    token = create_access_token({"sub": "usr-inactive-102"})
    headers = {"Authorization": f"Bearer {token}"}

    # Initial request: INACTIVE -> 403
    res1 = client.get("/protected/user-status", headers=headers)
    assert res1.status_code == 403

    # Reactivate user account
    user = db_session.query(User).filter(User.id == "usr-inactive-102").first()
    user.status = AccountStatus.ACTIVE
    db_session.commit()

    # Next request: now ACTIVE -> 200 OK
    res2 = client.get("/protected/user-status", headers=headers)
    assert res2.status_code == 200
    assert res2.json()["data"]["status"] == "ACTIVE"

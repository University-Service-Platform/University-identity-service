import pytest
from app.models.user import User, AccountType, AccountStatus
from app.models.role import Role, UserRole

def seed_users(db_session):
    # Seed Role
    role_student = Role(id=1, name="STUDENT", description="Student Role")
    role_staff = Role(id=2, name="STAFF", description="Staff Role")
    db_session.add_all([role_student, role_staff])
    db_session.commit()

    # Seed Active Student User
    active_user = User(
        id="usr-active-001",
        university_id="STU001",
        name="John Student",
        email="john@kln.ac.lk",
        account_type=AccountType.STUDENT,
        status=AccountStatus.ACTIVE
    )
    # Seed Inactive Staff User
    inactive_user = User(
        id="usr-inactive-002",
        university_id="STF002",
        name="Jane Staff",
        email="jane@kln.ac.lk",
        account_type=AccountType.STAFF,
        status=AccountStatus.INACTIVE
    )
    db_session.add_all([active_user, inactive_user])
    db_session.commit()

    # Seed UserRole
    ur = UserRole(user_id="usr-active-001", role_id=1)
    db_session.add(ur)
    db_session.commit()

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_validate_valid_user(client, db_session):
    seed_users(db_session)
    response = client.get("/validation/users/usr-active-001")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user_id"] == "usr-active-001"
    assert data["data"]["university_id"] == "STU001"
    assert data["data"]["account_type"] == "STUDENT"
    assert data["data"]["status"] == "ACTIVE"
    assert data["data"]["is_valid"] is True
    assert "STUDENT" in data["data"]["roles"]

def test_validate_user_by_university_id(client, db_session):
    seed_users(db_session)
    response = client.get("/validation/users/STU001")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user_id"] == "usr-active-001"

def test_validate_unknown_user(client, db_session):
    seed_users(db_session)
    response = client.get("/validation/users/non-existent-user")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "USER_NOT_FOUND"

def test_validate_inactive_user(client, db_session):
    seed_users(db_session)
    # Default validation returns is_valid=False for inactive user
    response = client.get("/validation/users/usr-inactive-002")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "INACTIVE"
    assert data["data"]["is_valid"] is False

    # Validation with require_active=True returns 403
    response_active_req = client.get("/validation/users/usr-inactive-002?require_active=true")
    assert response_active_req.status_code == 403
    data_req = response_active_req.json()
    assert data_req["success"] is False
    assert data_req["error"]["code"] == "ACCOUNT_INACTIVE"

def test_validate_malformed_identifier(client, db_session):
    seed_users(db_session)
    response = client.get("/validation/users/a!@#$%^&*")
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_IDENTIFIER_FORMAT"

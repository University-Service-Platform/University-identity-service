import pytest
from app.models.user import User, AccountType, AccountStatus
from app.models.role import Role, UserRole
from app.dependencies.auth import create_access_token

def seed_role_users(db_session):
    role_admin = Role(id=10, name="ADMIN", description="Administrator Role")
    role_dean = Role(id=11, name="DEAN", description="Dean Role")
    db_session.add_all([role_admin, role_dean])
    db_session.commit()

    user_admin = User(
        id="usr-role-201",
        university_id="ADM201",
        name="Admin User",
        email="admin201@kln.ac.lk",
        account_type=AccountType.STAFF,
        status=AccountStatus.ACTIVE
    )
    user_no_role = User(
        id="usr-role-202",
        university_id="STU202",
        name="Student User",
        email="student202@kln.ac.lk",
        account_type=AccountType.STUDENT,
        status=AccountStatus.ACTIVE
    )
    db_session.add_all([user_admin, user_no_role])
    db_session.commit()

    # Assign ADMIN role to user_admin
    ur = UserRole(user_id="usr-role-201", role_id=10)
    db_session.add(ur)
    db_session.commit()

def test_get_role_valid_user_assigned_role(client, db_session):
    seed_role_users(db_session)
    token = create_access_token({"sub": "usr-role-201"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/users/usr-role-201/role", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user_id"] == "usr-role-201"
    assert data["data"]["university_id"] == "ADM201"
    assert "ADMIN" in data["data"]["roles"]
    assert data["data"]["primary_role"] == "ADMIN"

def test_get_role_fallback_account_type(client, db_session):
    seed_role_users(db_session)
    token = create_access_token({"sub": "usr-role-202"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/users/usr-role-202/role", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user_id"] == "usr-role-202"
    assert "STUDENT" in data["data"]["roles"]
    assert data["data"]["primary_role"] == "STUDENT"

def test_get_role_unknown_user(client, db_session):
    seed_role_users(db_session)
    token = create_access_token({"sub": "usr-role-201"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/users/non-existent-user/role", headers=headers)
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "USER_NOT_FOUND"

def test_get_role_malformed_user_id(client, db_session):
    seed_role_users(db_session)
    token = create_access_token({"sub": "usr-role-201"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/users/ab/role", headers=headers)
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_IDENTIFIER_FORMAT"

def test_get_role_unauthenticated(client):
    response = client.get("/users/usr-role-201/role")
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"

def test_role_update_immediate_reflection(client, db_session):
    """
    Integration test:
    1. User starts with ADMIN role.
    2. Role is updated in DB (simulating Pavithira's role assignment endpoint USM-58 / USM-94).
    3. Next call to GET /users/{user_id}/role immediately reflects the updated role DEAN.
    """
    seed_role_users(db_session)
    token = create_access_token({"sub": "usr-role-201"})
    headers = {"Authorization": f"Bearer {token}"}

    # Initial check: ADMIN
    res1 = client.get("/users/usr-role-201/role", headers=headers)
    assert res1.status_code == 200
    assert res1.json()["data"]["primary_role"] == "ADMIN"

    # Simulate role reassignment (change role_id 10 to 11 DEAN)
    user_role = db_session.query(UserRole).filter(UserRole.user_id == "usr-role-201").first()
    user_role.role_id = 11
    db_session.commit()

    # Second check: DEAN reflected immediately
    res2 = client.get("/users/usr-role-201/role", headers=headers)
    assert res2.status_code == 200
    assert res2.json()["data"]["primary_role"] == "DEAN"
    assert "DEAN" in res2.json()["data"]["roles"]

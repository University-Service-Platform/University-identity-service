import pytest
from app.models.user import User, AccountType, AccountStatus
from app.models.role import Role, UserRole
from app.dependencies.auth import create_access_token

def seed_profile_users(db_session):
    role_admin = Role(id=400, name="ADMIN", description="Admin Role")
    role_student = Role(id=401, name="STUDENT", description="Student Role")
    db_session.add_all([role_admin, role_student])
    db_session.commit()

    student1 = User(
        id="usr-profile-401",
        university_id="STU401",
        name="Student One",
        email="student401@kln.ac.lk",
        account_type=AccountType.STUDENT,
        status=AccountStatus.ACTIVE
    )
    student2 = User(
        id="usr-profile-402",
        university_id="STU402",
        name="Student Two",
        email="student402@kln.ac.lk",
        account_type=AccountType.STUDENT,
        status=AccountStatus.ACTIVE
    )
    admin = User(
        id="usr-profile-403",
        university_id="ADM403",
        name="Admin User",
        email="admin403@kln.ac.lk",
        account_type=AccountType.STAFF,
        status=AccountStatus.ACTIVE
    )
    inactive_user = User(
        id="usr-profile-404",
        university_id="STU404",
        name="Inactive Student",
        email="inactive404@kln.ac.lk",
        account_type=AccountType.STUDENT,
        status=AccountStatus.INACTIVE
    )
    db_session.add_all([student1, student2, admin, inactive_user])
    db_session.commit()

    ur1 = UserRole(user_id="usr-profile-401", role_id=401)
    ur2 = UserRole(user_id="usr-profile-402", role_id=401)
    ur3 = UserRole(user_id="usr-profile-403", role_id=400)
    db_session.add_all([ur1, ur2, ur3])
    db_session.commit()

def test_self_profile_access(client, db_session):
    seed_profile_users(db_session)
    token = create_access_token({"sub": "usr-profile-401"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/users/usr-profile-401", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user_id"] == "usr-profile-401"
    assert data["data"]["name"] == "Student One"

def test_admin_profile_access_any_user(client, db_session):
    seed_profile_users(db_session)
    token = create_access_token({"sub": "usr-profile-403"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/users/usr-profile-401", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user_id"] == "usr-profile-401"

def test_unauthorized_student_access_other_profile(client, db_session):
    seed_profile_users(db_session)
    token = create_access_token({"sub": "usr-profile-401"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/users/usr-profile-402", headers=headers)
    assert response.status_code == 403
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "FORBIDDEN_PROFILE_ACCESS"

def test_unauthenticated_profile_access(client):
    response = client.get("/users/usr-profile-401")
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"

def test_inactive_account_profile_access(client, db_session):
    seed_profile_users(db_session)
    token = create_access_token({"sub": "usr-profile-404"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/users/usr-profile-404", headers=headers)
    assert response.status_code == 403
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "ACCOUNT_INACTIVE"

def test_non_existent_profile_access(client, db_session):
    seed_profile_users(db_session)
    token = create_access_token({"sub": "usr-profile-403"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/users/non-existent-usr", headers=headers)
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "USER_NOT_FOUND"

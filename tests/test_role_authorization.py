import pytest
from app.models.user import User, AccountType, AccountStatus
from app.models.role import Role, UserRole
from app.dependencies.auth import create_access_token

def seed_role_auth_users(db_session):
    role_admin = Role(id=100, name="ADMIN", description="Admin Role")
    role_staff = Role(id=101, name="STAFF", description="Staff Role")
    role_student = Role(id=102, name="STUDENT", description="Student Role")
    db_session.add_all([role_admin, role_staff, role_student])
    db_session.commit()

    user_admin = User(
        id="usr-admin-301",
        university_id="ADM301",
        name="Admin Person",
        email="admin301@kln.ac.lk",
        account_type=AccountType.STAFF,
        status=AccountStatus.ACTIVE
    )
    user_student = User(
        id="usr-student-302",
        university_id="STU302",
        name="Student Person",
        email="student302@kln.ac.lk",
        account_type=AccountType.STUDENT,
        status=AccountStatus.ACTIVE
    )
    user_inactive_admin = User(
        id="usr-inactive-admin-303",
        university_id="ADM303",
        name="Inactive Admin",
        email="inactive303@kln.ac.lk",
        account_type=AccountType.STAFF,
        status=AccountStatus.INACTIVE
    )
    db_session.add_all([user_admin, user_student, user_inactive_admin])
    db_session.commit()

    # Assign roles
    ur1 = UserRole(user_id="usr-admin-301", role_id=100)
    ur2 = UserRole(user_id="usr-student-302", role_id=102)
    ur3 = UserRole(user_id="usr-inactive-admin-303", role_id=100)
    db_session.add_all([ur1, ur2, ur3])
    db_session.commit()

def test_admin_role_access_granted(client, db_session):
    seed_role_auth_users(db_session)
    token = create_access_token({"sub": "usr-admin-301"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/protected/admin-only", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user_id"] == "usr-admin-301"

def test_insufficient_role_denied(client, db_session):
    seed_role_auth_users(db_session)
    token = create_access_token({"sub": "usr-student-302"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/protected/admin-only", headers=headers)
    assert response.status_code == 403
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

def test_staff_or_admin_multi_role_access(client, db_session):
    seed_role_auth_users(db_session)
    token = create_access_token({"sub": "usr-admin-301"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/protected/staff-only", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

def test_unauthenticated_role_request(client):
    response = client.get("/protected/admin-only")
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"

def test_inactive_user_role_request(client, db_session):
    seed_role_auth_users(db_session)
    token = create_access_token({"sub": "usr-inactive-admin-303"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/protected/admin-only", headers=headers)
    assert response.status_code == 403
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "ACCOUNT_INACTIVE"

def test_immediate_role_upgrade_integration(client, db_session):
    """
    Integration test:
    1. Student user tries admin-only route -> 403 INSUFFICIENT_PERMISSIONS.
    2. Admin updates role in DB to ADMIN (simulating Pavithira's role assignment endpoint USM-58).
    3. Next request to admin-only route succeeds with 200 OK.
    """
    seed_role_auth_users(db_session)
    token = create_access_token({"sub": "usr-student-302"})
    headers = {"Authorization": f"Bearer {token}"}

    # Initial request: STUDENT role -> 403
    res1 = client.get("/protected/admin-only", headers=headers)
    assert res1.status_code == 403

    # Upgrade role in DB to ADMIN (role_id 100)
    user_role = db_session.query(UserRole).filter(UserRole.user_id == "usr-student-302").first()
    user_role.role_id = 100
    db_session.commit()

    # Next request: now ADMIN -> 200 OK
    res2 = client.get("/protected/admin-only", headers=headers)
    assert res2.status_code == 200
    assert res2.json()["data"]["user_id"] == "usr-student-302"

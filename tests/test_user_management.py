import pytest
from app.models.user import User, AccountType, AccountStatus
from app.models.role import Role, UserRole
from app.dependencies.auth import create_access_token

def seed_management_users(db_session):
    # Seed prototype roles
    role_admin = Role(id=1, name="ADMIN", description="Administrator Role")
    role_staff = Role(id=2, name="STAFF", description="Staff Member Role")
    role_student = Role(id=3, name="STUDENT", description="Student Role")
    db_session.add_all([role_admin, role_staff, role_student])
    db_session.commit()

    # Seed Admin User
    admin_user = User(
        id="usr-admin-mgr-001",
        university_id="ADM001",
        name="System Admin",
        email="admin@kln.ac.lk",
        account_type=AccountType.STAFF,
        status=AccountStatus.ACTIVE
    )
    # Seed Regular Staff User
    staff_user = User(
        id="usr-staff-mgr-002",
        university_id="STF002",
        name="Staff Member",
        email="staff@kln.ac.lk",
        account_type=AccountType.STAFF,
        status=AccountStatus.ACTIVE
    )
    # Seed Student User
    student_user = User(
        id="usr-student-mgr-003",
        university_id="STU003",
        name="Student Person",
        email="student@kln.ac.lk",
        account_type=AccountType.STUDENT,
        status=AccountStatus.ACTIVE
    )
    db_session.add_all([admin_user, staff_user, student_user])
    db_session.commit()

    # Assign roles
    ur1 = UserRole(user_id="usr-admin-mgr-001", role_id=1)
    ur2 = UserRole(user_id="usr-staff-mgr-002", role_id=2)
    ur3 = UserRole(user_id="usr-student-mgr-003", role_id=3)
    db_session.add_all([ur1, ur2, ur3])
    db_session.commit()

def test_admin_creates_student_account(client, db_session):
    seed_management_users(db_session)
    token = create_access_token({"sub": "usr-admin-mgr-001"})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "university_id": "STU100",
        "name": "Alice Perera",
        "email": "alice.perera@kln.ac.lk",
        "account_type": "STUDENT"
    }

    response = client.post("/users", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["university_id"] == "STU100"
    assert data["data"]["name"] == "Alice Perera"
    assert data["data"]["email"] == "alice.perera@kln.ac.lk"
    assert data["data"]["account_type"] == "STUDENT"
    assert data["data"]["status"] == "ACTIVE"
    assert "id" in data["data"]
    assert "STUDENT" in data["data"]["roles"]

def test_admin_creates_staff_account(client, db_session):
    seed_management_users(db_session)
    token = create_access_token({"sub": "usr-admin-mgr-001"})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "university_id": "STF200",
        "name": "Dr. Fernando",
        "email": "fernando@kln.ac.lk",
        "account_type": "STAFF"
    }

    response = client.post("/users", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["university_id"] == "STF200"
    assert data["data"]["name"] == "Dr. Fernando"
    assert data["data"]["account_type"] == "STAFF"
    assert data["data"]["status"] == "ACTIVE"
    assert "STAFF" in data["data"]["roles"]

def test_create_user_invalid_account_type(client, db_session):
    seed_management_users(db_session)
    token = create_access_token({"sub": "usr-admin-mgr-001"})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "university_id": "GUEST001",
        "name": "Invalid Guest",
        "email": "guest@kln.ac.lk",
        "account_type": "GUEST"
    }

    response = client.post("/users", json=payload, headers=headers)
    assert response.status_code == 422

def test_create_user_duplicate_university_id(client, db_session):
    seed_management_users(db_session)
    token = create_access_token({"sub": "usr-admin-mgr-001"})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "university_id": "STU003",  # Already assigned to student_user
        "name": "Duplicate Student",
        "email": "dupstudent@kln.ac.lk",
        "account_type": "STUDENT"
    }

    response = client.post("/users", json=payload, headers=headers)
    assert response.status_code == 409
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNIVERSITY_ID_ALREADY_EXISTS"

def test_create_user_duplicate_email(client, db_session):
    seed_management_users(db_session)
    token = create_access_token({"sub": "usr-admin-mgr-001"})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "university_id": "STU105",
        "name": "New Student",
        "email": "student@kln.ac.lk",  # Already assigned to student_user
        "account_type": "STUDENT"
    }

    response = client.post("/users", json=payload, headers=headers)
    assert response.status_code == 409
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "EMAIL_ALREADY_EXISTS"

def test_unauthorized_user_cannot_create_account(client, db_session):
    seed_management_users(db_session)

    payload = {
        "university_id": "STU999",
        "name": "Unauthorized Creation",
        "email": "unauth@kln.ac.lk",
        "account_type": "STUDENT"
    }

    # 1. Unauthenticated request -> 401
    res_no_auth = client.post("/users", json=payload)
    assert res_no_auth.status_code == 401

    # 2. Student user attempting to create account -> 403
    student_token = create_access_token({"sub": "usr-student-mgr-003"})
    res_student = client.post(
        "/users",
        json=payload,
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert res_student.status_code == 403
    assert res_student.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

def test_list_users_authorization(client, db_session):
    seed_management_users(db_session)

    admin_token = create_access_token({"sub": "usr-admin-mgr-001"})
    staff_token = create_access_token({"sub": "usr-staff-mgr-002"})
    student_token = create_access_token({"sub": "usr-student-mgr-003"})

    # Admin can list users
    res_admin = client.get("/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    assert res_admin.json()["success"] is True
    assert len(res_admin.json()["data"]) >= 3

    # Staff can list users
    res_staff = client.get("/users", headers={"Authorization": f"Bearer {staff_token}"})
    assert res_staff.status_code == 200
    assert res_staff.json()["success"] is True

    # Student cannot list users -> 403
    res_student = client.get("/users", headers={"Authorization": f"Bearer {student_token}"})
    assert res_student.status_code == 403

def test_existing_get_user_profile_preserved(client, db_session):
    seed_management_users(db_session)

    admin_token = create_access_token({"sub": "usr-admin-mgr-001"})
    student_token = create_access_token({"sub": "usr-student-mgr-003"})

    # Student accessing their own profile -> 200
    res_self = client.get(
        "/users/usr-student-mgr-003",
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert res_self.status_code == 200
    assert res_self.json()["data"]["name"] == "Student Person"

    # Admin accessing student profile -> 200
    res_admin = client.get(
        "/users/usr-student-mgr-003",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["data"]["university_id"] == "STU003"

def test_admin_updates_permitted_account_fields(client, db_session):
    seed_management_users(db_session)
    token = create_access_token({"sub": "usr-admin-mgr-001"})
    headers = {"Authorization": f"Bearer {token}"}

    update_payload = {
        "name": "Updated Student Name",
        "email": "updated.student@kln.ac.lk"
    }

    response = client.put(
        "/users/usr-student-mgr-003",
        json=update_payload,
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Updated Student Name"
    assert data["data"]["email"] == "updated.student@kln.ac.lk"
    # University ID remains unchanged and immutable
    assert data["data"]["university_id"] == "STU003"

def test_unauthorized_user_cannot_update_account(client, db_session):
    seed_management_users(db_session)
    student_token = create_access_token({"sub": "usr-student-mgr-003"})

    update_payload = {
        "name": "Hacked Name"
    }

    response = client.put(
        "/users/usr-admin-mgr-001",
        json=update_payload,
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

def test_update_user_conflict_and_validation(client, db_session):
    seed_management_users(db_session)
    admin_token = create_access_token({"sub": "usr-admin-mgr-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Attempt to update to an email that is already taken by another user
    conflict_payload = {
        "email": "admin@kln.ac.lk"
    }
    res_conflict = client.put(
        "/users/usr-student-mgr-003",
        json=conflict_payload,
        headers=headers
    )
    assert res_conflict.status_code == 409
    assert res_conflict.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"

    # Non-existent user -> 404
    res_404 = client.put(
        "/users/non-existent-user",
        json={"name": "Nobody"},
        headers=headers
    )
    assert res_404.status_code == 404

def test_admin_deletes_user_account(client, db_session):
    seed_management_users(db_session)
    admin_token = create_access_token({"sub": "usr-admin-mgr-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Delete student
    response = client.delete("/users/usr-student-mgr-003", headers=headers)
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Subsequent fetch returns 404
    fetch_res = client.get("/users/usr-student-mgr-003", headers=headers)
    assert fetch_res.status_code == 404

    # Confirm user_roles association was deleted (no orphan)
    orphan_roles = db_session.query(UserRole).filter(UserRole.user_id == "usr-student-mgr-003").all()
    assert len(orphan_roles) == 0

def test_unauthorized_user_cannot_delete_account(client, db_session):
    seed_management_users(db_session)
    student_token = create_access_token({"sub": "usr-student-mgr-003"})

    # Student trying to delete admin account -> 403
    response = client.delete(
        "/users/usr-admin-mgr-001",
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

import pytest
from app.models.user import User, AccountType, AccountStatus
from app.models.role import Role, UserRole
from app.dependencies.auth import create_access_token

def seed_status_test_data(db_session):
    # Seed prototype roles
    role_admin = Role(id=1, name="ADMIN", description="Administrator Role")
    role_staff = Role(id=2, name="STAFF", description="Staff Member Role")
    role_student = Role(id=3, name="STUDENT", description="Student Role")
    db_session.add_all([role_admin, role_staff, role_student])
    db_session.commit()

    # Seed Admin User
    admin_user = User(
        id="usr-admin-status-001",
        university_id="ADM001",
        name="Admin User",
        email="admin@kln.ac.lk",
        account_type=AccountType.STAFF,
        status=AccountStatus.ACTIVE
    )
    # Seed Staff User
    staff_user = User(
        id="usr-staff-status-002",
        university_id="STF002",
        name="Staff User",
        email="staff@kln.ac.lk",
        account_type=AccountType.STAFF,
        status=AccountStatus.ACTIVE
    )
    # Seed Active Student User
    student_active = User(
        id="usr-student-active-003",
        university_id="STU003",
        name="Active Student",
        email="student.active@kln.ac.lk",
        account_type=AccountType.STUDENT,
        status=AccountStatus.ACTIVE
    )
    # Seed Inactive Student User
    student_inactive = User(
        id="usr-student-inactive-004",
        university_id="STU004",
        name="Inactive Student",
        email="student.inactive@kln.ac.lk",
        account_type=AccountType.STUDENT,
        status=AccountStatus.INACTIVE
    )
    db_session.add_all([admin_user, staff_user, student_active, student_inactive])
    db_session.commit()

    # Assign roles
    ur1 = UserRole(user_id="usr-admin-status-001", role_id=1)
    ur2 = UserRole(user_id="usr-staff-status-002", role_id=2)
    ur3 = UserRole(user_id="usr-student-active-003", role_id=3)
    ur4 = UserRole(user_id="usr-student-inactive-004", role_id=3)
    db_session.add_all([ur1, ur2, ur3, ur4])
    db_session.commit()

def test_admin_deactivates_active_user(client, db_session):
    seed_status_test_data(db_session)
    token = create_access_token({"sub": "usr-admin-status-001"})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"status": "INACTIVE"}
    response = client.patch(
        "/users/usr-student-active-003/status",
        json=payload,
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == "usr-student-active-003"
    assert data["data"]["status"] == "INACTIVE"

    # Verify directly in the database
    db_user = db_session.query(User).filter(User.id == "usr-student-active-003").first()
    assert db_user.status == AccountStatus.INACTIVE

def test_admin_activates_inactive_user(client, db_session):
    seed_status_test_data(db_session)
    token = create_access_token({"sub": "usr-admin-status-001"})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"status": "ACTIVE"}
    response = client.patch(
        "/users/usr-student-inactive-004/status",
        json=payload,
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == "usr-student-inactive-004"
    assert data["data"]["status"] == "ACTIVE"

    # Verify directly in the database
    db_user = db_session.query(User).filter(User.id == "usr-student-inactive-004").first()
    assert db_user.status == AccountStatus.ACTIVE

def test_staff_cannot_deactivate_user(client, db_session):
    seed_status_test_data(db_session)
    staff_token = create_access_token({"sub": "usr-staff-status-002"})
    headers = {"Authorization": f"Bearer {staff_token}"}

    payload = {"status": "INACTIVE"}
    response = client.patch(
        "/users/usr-student-active-003/status",
        json=payload,
        headers=headers
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

def test_student_cannot_activate_user(client, db_session):
    seed_status_test_data(db_session)
    student_token = create_access_token({"sub": "usr-student-active-003"})
    headers = {"Authorization": f"Bearer {student_token}"}

    payload = {"status": "ACTIVE"}
    response = client.patch(
        "/users/usr-student-inactive-004/status",
        json=payload,
        headers=headers
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

def test_unauthenticated_status_change_rejected(client, db_session):
    seed_status_test_data(db_session)

    payload = {"status": "INACTIVE"}
    response = client.patch("/users/usr-student-active-003/status", json=payload)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"

def test_status_change_nonexistent_user(client, db_session):
    seed_status_test_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-status-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {"status": "INACTIVE"}
    response = client.patch(
        "/users/non-existent-user-id/status",
        json=payload,
        headers=headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"

def test_status_change_invalid_status_value(client, db_session):
    seed_status_test_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-status-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {"status": "SUSPENDED"}  # Invalid enum value
    response = client.patch(
        "/users/usr-student-active-003/status",
        json=payload,
        headers=headers
    )
    assert response.status_code == 422

def test_immediate_deactivation_and_reactivation_enforcement(client, db_session):
    """
    End-to-End Integration Flow:
    1. Active student has valid token and accesses protected endpoint -> 200 OK.
    2. Admin deactivates student via PATCH /users/{user_id}/status -> 200 OK.
    3. Same student with same token immediately calls protected endpoint -> 403 ACCOUNT_INACTIVE.
    4. Admin reactivates student via PATCH /users/{user_id}/status -> 200 OK.
    5. Same student with same token calls protected endpoint again -> 200 OK.
    """
    seed_status_test_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-status-001"})
    student_token = create_access_token({"sub": "usr-student-active-003"})

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # Step 1: Initial access while ACTIVE succeeds
    res1 = client.get("/protected/user-status", headers=student_headers)
    assert res1.status_code == 200
    assert res1.json()["data"]["status"] == "ACTIVE"

    # Step 2: Admin deactivates account via USM-47 API
    res_deactivate = client.patch(
        "/users/usr-student-active-003/status",
        json={"status": "INACTIVE"},
        headers=admin_headers
    )
    assert res_deactivate.status_code == 200
    assert res_deactivate.json()["data"]["status"] == "INACTIVE"

    # Step 3: Immediate rejection on next request with existing token
    res2 = client.get("/protected/user-status", headers=student_headers)
    assert res2.status_code == 403
    assert res2.json()["error"]["code"] == "ACCOUNT_INACTIVE"

    # Step 4: Admin reactivates account via USM-47 API
    res_reactivate = client.patch(
        "/users/usr-student-active-003/status",
        json={"status": "ACTIVE"},
        headers=admin_headers
    )
    assert res_reactivate.status_code == 200
    assert res_reactivate.json()["data"]["status"] == "ACTIVE"

    # Step 5: Subsequent request immediately succeeds
    res3 = client.get("/protected/user-status", headers=student_headers)
    assert res3.status_code == 200
    assert res3.json()["data"]["status"] == "ACTIVE"

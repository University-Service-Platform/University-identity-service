import pytest
from app.models.user import User, AccountType, AccountStatus
from app.models.role import Role, UserRole
from app.dependencies.auth import create_access_token

def seed_role_assignment_data(db_session):
    # Seed prototype and test roles
    role_admin = Role(id=1, name="ADMIN", description="Administrator Role")
    role_staff = Role(id=2, name="STAFF", description="Staff Member Role")
    role_student = Role(id=3, name="STUDENT", description="Student Role")
    role_dean = Role(id=4, name="DEAN", description="Dean Role")
    db_session.add_all([role_admin, role_staff, role_student, role_dean])
    db_session.commit()

    # Seed Admin User
    admin_user = User(
        id="usr-admin-role-001",
        university_id="ADM001",
        name="Admin Person",
        email="admin@kln.ac.lk",
        account_type=AccountType.STAFF,
        status=AccountStatus.ACTIVE
    )
    # Seed Staff User
    staff_user = User(
        id="usr-staff-role-002",
        university_id="STF002",
        name="Staff Person",
        email="staff@kln.ac.lk",
        account_type=AccountType.STAFF,
        status=AccountStatus.ACTIVE
    )
    # Seed Student User
    student_user = User(
        id="usr-student-role-003",
        university_id="STU003",
        name="Student Person",
        email="student@kln.ac.lk",
        account_type=AccountType.STUDENT,
        status=AccountStatus.ACTIVE
    )
    db_session.add_all([admin_user, staff_user, student_user])
    db_session.commit()

    # Assign initial roles
    ur1 = UserRole(user_id="usr-admin-role-001", role_id=1)  # ADMIN
    ur2 = UserRole(user_id="usr-staff-role-002", role_id=2)  # STAFF
    ur3 = UserRole(user_id="usr-student-role-003", role_id=3) # STUDENT
    db_session.add_all([ur1, ur2, ur3])
    db_session.commit()

def test_admin_assigns_existing_role(client, db_session):
    seed_role_assignment_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-role-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {"role_name": "DEAN"}
    response = client.post(
        "/users/usr-staff-role-002/roles",
        json=payload,
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user_id"] == "usr-staff-role-002"
    assert "DEAN" in data["data"]["roles"]
    assert "STAFF" in data["data"]["roles"]

    # Verify directly in DB
    user_roles = (
        db_session.query(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == "usr-staff-role-002")
        .all()
    )
    role_names = [r[0] for r in user_roles]
    assert "DEAN" in role_names

def test_duplicate_role_assignment_rejected(client, db_session):
    seed_role_assignment_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-role-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {"role_name": "STUDENT"}
    response = client.post(
        "/users/usr-student-role-003/roles",
        json=payload,
        headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ROLE_ALREADY_ASSIGNED"

def test_nonexistent_role_rejected(client, db_session):
    seed_role_assignment_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-role-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {"role_name": "CHANCELLOR"}
    response = client.post(
        "/users/usr-student-role-003/roles",
        json=payload,
        headers=headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ROLE_NOT_FOUND"

def test_nonexistent_user_assignment_rejected(client, db_session):
    seed_role_assignment_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-role-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {"role_name": "STAFF"}
    response = client.post(
        "/users/non-existent-user-id/roles",
        json=payload,
        headers=headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"

def test_staff_cannot_assign_role(client, db_session):
    seed_role_assignment_data(db_session)
    staff_token = create_access_token({"sub": "usr-staff-role-002"})
    headers = {"Authorization": f"Bearer {staff_token}"}

    payload = {"role_name": "ADMIN"}
    response = client.post(
        "/users/usr-student-role-003/roles",
        json=payload,
        headers=headers
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

def test_student_cannot_assign_role(client, db_session):
    seed_role_assignment_data(db_session)
    student_token = create_access_token({"sub": "usr-student-role-003"})
    headers = {"Authorization": f"Bearer {student_token}"}

    payload = {"role_name": "ADMIN"}
    response = client.post(
        "/users/usr-student-role-003/roles",
        json=payload,
        headers=headers
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

def test_unauthenticated_assignment_rejected(client, db_session):
    seed_role_assignment_data(db_session)

    payload = {"role_name": "STAFF"}
    response = client.post("/users/usr-student-role-003/roles", json=payload)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"

def test_admin_updates_user_role_relationship_success(client, db_session):
    """
    USM-94 Acceptance Criteria:
    - Given an authorized administrator, an existing user-role relationship can be updated.
    """
    seed_role_assignment_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-role-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Update staff_user role from STAFF to DEAN via PUT /users/{user_id}/roles
    payload = {
        "old_role_name": "STAFF",
        "new_role_name": "DEAN"
    }
    response = client.put(
        "/users/usr-staff-role-002/roles",
        json=payload,
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user_id"] == "usr-staff-role-002"
    assert "DEAN" in data["data"]["roles"]
    assert "STAFF" not in data["data"]["roles"]

def test_update_role_nonexistent_target_role_rejected(client, db_session):
    seed_role_assignment_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-role-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {
        "old_role_name": "STAFF",
        "new_role_name": "NON_EXISTENT_ROLE"
    }
    response = client.put(
        "/users/usr-staff-role-002/roles",
        json=payload,
        headers=headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ROLE_NOT_FOUND"

def test_update_role_unassigned_old_role_rejected(client, db_session):
    seed_role_assignment_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-role-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Staff user does not possess ADMIN role to update
    payload = {
        "old_role_name": "ADMIN",
        "new_role_name": "DEAN"
    }
    response = client.put(
        "/users/usr-staff-role-002/roles",
        json=payload,
        headers=headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ROLE_NOT_ASSIGNED"

def test_unauthorized_user_cannot_update_role(client, db_session):
    seed_role_assignment_data(db_session)
    student_token = create_access_token({"sub": "usr-student-role-003"})
    headers = {"Authorization": f"Bearer {student_token}"}

    payload = {
        "old_role_name": "STAFF",
        "new_role_name": "ADMIN"
    }
    response = client.put(
        "/users/usr-staff-role-002/roles",
        json=payload,
        headers=headers
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

def test_updated_role_authorization_applies_immediately(client, db_session):
    """
    USM-94 Acceptance Criteria:
    - Updated authorization must apply to subsequent protected requests.
    """
    seed_role_assignment_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-role-001"})
    staff_token = create_access_token({"sub": "usr-staff-role-002"})

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # Staff user initially denied on /protected/admin-only
    res1 = client.get("/protected/admin-only", headers=staff_headers)
    assert res1.status_code == 403

    # Admin updates staff_user role from STAFF to ADMIN
    payload = {
        "old_role_name": "STAFF",
        "new_role_name": "ADMIN"
    }
    res_update = client.put(
        "/users/usr-staff-role-002/roles",
        json=payload,
        headers=admin_headers
    )
    assert res_update.status_code == 200

    # Same staff user immediately accesses /protected/admin-only -> 200 OK
    res2 = client.get("/protected/admin-only", headers=staff_headers)
    assert res2.status_code == 200
    assert res2.json()["data"]["user_id"] == "usr-staff-role-002"

def test_admin_revokes_assigned_role(client, db_session):
    seed_role_assignment_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-role-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    client.post("/users/usr-staff-role-002/roles", json={"role_name": "DEAN"}, headers=headers)

    response = client.delete("/users/usr-staff-role-002/roles/DEAN", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "DEAN" not in data["data"]["roles"]
    assert "STAFF" in data["data"]["roles"]

def test_revoking_unassigned_role_rejected(client, db_session):
    seed_role_assignment_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-role-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.delete("/users/usr-staff-role-002/roles/DEAN", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ROLE_NOT_ASSIGNED"

def test_staff_cannot_revoke_role(client, db_session):
    seed_role_assignment_data(db_session)
    staff_token = create_access_token({"sub": "usr-staff-role-002"})
    headers = {"Authorization": f"Bearer {staff_token}"}

    response = client.delete("/users/usr-student-role-003/roles/STUDENT", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

def test_student_cannot_revoke_role(client, db_session):
    seed_role_assignment_data(db_session)
    student_token = create_access_token({"sub": "usr-student-role-003"})
    headers = {"Authorization": f"Bearer {student_token}"}

    response = client.delete("/users/usr-admin-role-001/roles/ADMIN", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

def test_unauthenticated_revocation_rejected(client, db_session):
    seed_role_assignment_data(db_session)
    response = client.delete("/users/usr-student-role-003/roles/STUDENT")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"

def test_malformed_user_id_assignment_rejected(client, db_session):
    seed_role_assignment_data(db_session)
    admin_token = create_access_token({"sub": "usr-admin-role-001"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {"role_name": "STAFF"}
    response = client.post(
        "/users/a!@/roles",
        json=payload,
        headers=headers
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_IDENTIFIER_FORMAT"

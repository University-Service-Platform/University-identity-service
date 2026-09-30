"""GET/PUT /api/v1/users/profile (the shared frontend's profile page) and the derived first/last name fields."""
from app.models.audit_log import AuditLog
from app.schemas.names import split_name
from tests.helpers import auth_header, create_user


def test_split_name():
    assert split_name("Demo System Administrator") == ("Demo", "System Administrator")
    assert split_name("Madonna") == ("Madonna", "")
    assert split_name("  Ann   Lee ") == ("Ann", "Lee")


def test_get_own_profile(client, db_session):
    user = create_user(db_session, "usr-own-01", role="STUDENT")
    response = client.get("/api/v1/users/profile", headers=auth_header(user.id))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user_id"] == "usr-own-01"
    assert data["roles"] == ["STUDENT"]
    assert (data["first_name"], data["last_name"]) == ("Test", "usr-own-01")


def test_get_own_profile_needs_a_token(client, db_session):
    assert client.get("/api/v1/users/profile").status_code == 401


def test_update_own_name_with_frontend_fields(client, db_session):
    user = create_user(db_session, "usr-own-02", role="STUDENT")
    response = client.put("/api/v1/users/profile", headers=auth_header(user.id), json={
        "firstName": "Nimal", "lastName": "Perera", "email": user.email, "phone": "+94 71 234 5678"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["name"], data["first_name"], data["last_name"]) == ("Nimal Perera", "Nimal", "Perera")
    log = db_session.query(AuditLog).filter(AuditLog.action == "USER_UPDATED").one()
    assert log.actor_user_id == log.target_id == user.id


def test_update_own_profile_cannot_change_email(client, db_session):
    user = create_user(db_session, "usr-own-03", role="STUDENT")
    response = client.put("/api/v1/users/profile", headers=auth_header(user.id),
                          json={"firstName": "X", "lastName": "Y", "email": "someone.else@university.example"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "EMAIL_CHANGE_NOT_ALLOWED"
    db_session.refresh(user)
    assert user.name == "Test usr-own-03"


def test_update_own_profile_does_not_touch_other_fields(client, db_session):
    user = create_user(db_session, "usr-own-04", role="STUDENT")
    response = client.put("/api/v1/users/profile", headers=auth_header(user.id),
                          json={"name": "New Name", "account_type": "STUDENT", "status": "INACTIVE"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "New Name"
    assert data["account_type"] == "STAFF" and data["status"] == "ACTIVE"


def test_current_identity_and_user_list_include_name_parts(client, db_session):
    admin = create_user(db_session, "usr-own-05", role="ADMIN")
    me = client.get("/api/v1/auth/me", headers=auth_header(admin.id)).json()["data"]
    assert (me["first_name"], me["last_name"]) == ("Test", "usr-own-05")
    users = client.get("/api/v1/users", headers=auth_header(admin.id)).json()["data"]
    assert all("first_name" in u and "last_name" in u for u in users)

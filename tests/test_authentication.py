from dataclasses import replace
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app.core.config import get_settings
from app.core.security import get_signing_keys, hash_password, verify_password
from app.dependencies.auth import create_access_token
from app.models.user import AccountStatus, AccountType
from app.reference_data import ensure_reference_data
from tests.helpers import auth_header, create_user

PASSWORD = "Correct-Horse-9"


@pytest.fixture
def reference_data(db_session):
    ensure_reference_data(db_session)
    return db_session


def user_with_password(db, user_id, role="STUDENT", status=AccountStatus.ACTIVE):
    user = create_user(db, user_id, role=role, account_type=AccountType.STUDENT, status=status)
    user.password_hash = hash_password(PASSWORD)
    db.commit()
    return user


def login(client, username, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


# ---------------------------------------------------------------- login

def test_login_with_university_id_issues_documented_claims(client, reference_data):
    user = user_with_password(reference_data, "usr-login-01", role="STUDENT")

    response = login(client, user.university_id)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == get_settings().access_token_expire_minutes * 60
    assert data["roles"] == ["STUDENT"]

    claims = jwt.get_unverified_claims(data["access_token"])
    assert claims["sub"] == user.id
    assert claims["university_id"] == user.university_id
    assert claims["account_type"] == "STUDENT"
    assert claims["roles"] == ["STUDENT"]
    assert claims["iss"] == get_settings().jwt_issuer
    assert claims["aud"] == get_settings().jwt_audience
    assert {"iat", "exp"} <= set(claims)


def test_login_with_email_is_case_insensitive(client, reference_data):
    user = user_with_password(reference_data, "usr-login-02")
    assert login(client, user.email.upper()).status_code == 200


def test_login_token_grants_access_to_protected_endpoint(client, reference_data):
    user = user_with_password(reference_data, "usr-login-03")
    token = login(client, user.university_id).json()["data"]["access_token"]

    response = client.get("/protected/user-status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


@pytest.mark.parametrize("username,password", [
    ("UNI-LOGIN-04", "wrong-password"),   # wrong password
    ("NOBODY999", PASSWORD),              # unknown user
])
def test_invalid_credentials_share_one_response(client, reference_data, username, password):
    user_with_password(reference_data, "usr-login-04")
    response = login(client, username, password)
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "INVALID_CREDENTIALS"
    assert body["error"]["message"] == "Invalid university ID/email or password."


def test_account_without_password_cannot_log_in(client, reference_data):
    user = create_user(reference_data, "usr-login-05", role="STUDENT")
    response = login(client, user.university_id)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_inactive_account_cannot_log_in(client, reference_data):
    user = user_with_password(reference_data, "usr-login-06", status=AccountStatus.INACTIVE)
    response = login(client, user.university_id)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_INACTIVE"


# ---------------------------------------------------------------- token verification

def test_expired_token_is_rejected(client, reference_data):
    create_user(reference_data, "usr-token-07", role="STUDENT")
    token = create_access_token({"sub": "usr-token-07"}, expires_delta=timedelta(seconds=-5))
    response = client.get("/protected/user-status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_token_for_another_audience_is_rejected(client, reference_data):
    create_user(reference_data, "usr-token-08", role="STUDENT")
    keys = get_signing_keys()
    token = jwt.encode(
        {"sub": "usr-token-08", "iss": get_settings().jwt_issuer, "aud": "some-other-platform", "exp": 9999999999},
        keys.signing_key, algorithm=keys.algorithm,
    )
    response = client.get("/protected/user-status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_token_signed_with_foreign_key_is_rejected(client, reference_data):
    create_user(reference_data, "usr-token-09", role="STUDENT")
    foreign_key = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    token = jwt.encode(
        {"sub": "usr-token-09", "iss": get_settings().jwt_issuer, "aud": get_settings().jwt_audience, "exp": 9999999999},
        foreign_key.decode(), algorithm="RS256",
    )
    response = client.get("/protected/user-status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_token_without_subject_is_rejected(client, reference_data):
    token = create_access_token({"university_id": "NO-SUB"})
    response = client.get("/protected/user-status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_jwks_publishes_key_that_verifies_issued_tokens(client, reference_data):
    user = user_with_password(reference_data, "usr-jwks-10")
    token = login(client, user.university_id).json()["data"]["access_token"]

    jwks = client.get("/.well-known/jwks.json").json()
    assert len(jwks["keys"]) == 1
    key = jwks["keys"][0]
    assert key["kty"] == "RSA" and key["alg"] == "RS256" and key["use"] == "sig"
    assert jwt.get_unverified_header(token)["kid"] == key["kid"]

    claims = jwt.decode(token, key, algorithms=["RS256"], audience=get_settings().jwt_audience)
    assert claims["sub"] == user.id


# ---------------------------------------------------------------- passwords

def test_created_user_with_password_can_log_in_and_hash_is_never_returned(client, reference_data):
    create_user(reference_data, "usr-admin-pw-11", role="ADMIN")
    response = client.post(
        "/users",
        json={"university_id": "STU777", "name": "New Student", "email": "stu777@university.example",
              "account_type": "STUDENT", "password": PASSWORD},
        headers=auth_header("usr-admin-pw-11"),
    )
    assert response.status_code == 201
    assert "password" not in response.text
    assert login(client, "STU777").status_code == 200


def test_short_password_is_rejected(client, reference_data):
    create_user(reference_data, "usr-admin-pw-12", role="ADMIN")
    response = client.post(
        "/users",
        json={"university_id": "STU778", "name": "Short", "email": "stu778@university.example",
              "account_type": "STUDENT", "password": "short"},
        headers=auth_header("usr-admin-pw-12"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_admin_can_set_password_but_staff_cannot(client, reference_data):
    create_user(reference_data, "usr-admin-pw-13", role="ADMIN")
    create_user(reference_data, "usr-staff-pw-13", role="STAFF")
    target = create_user(reference_data, "usr-target-pw-13", role="STUDENT")
    body = {"new_password": PASSWORD}

    forbidden = client.put(f"/api/v1/users/{target.id}/password", json=body, headers=auth_header("usr-staff-pw-13"))
    assert forbidden.status_code == 403

    allowed = client.put(f"/api/v1/users/{target.id}/password", json=body, headers=auth_header("usr-admin-pw-13"))
    assert allowed.status_code == 200
    assert login(client, target.university_id).status_code == 200


def test_user_can_change_own_password(client, reference_data):
    user = user_with_password(reference_data, "usr-change-14")
    headers = auth_header(user.id)

    wrong = client.post("/api/v1/auth/change-password",
                        json={"current_password": "not-it", "new_password": "Brand-New-Pass-1"}, headers=headers)
    assert wrong.status_code == 400
    assert wrong.json()["error"]["code"] == "INVALID_CURRENT_PASSWORD"

    ok = client.post("/api/v1/auth/change-password",
                     json={"current_password": PASSWORD, "new_password": "Brand-New-Pass-1"}, headers=headers)
    assert ok.status_code == 200
    assert login(client, user.university_id).status_code == 401
    assert login(client, user.university_id, "Brand-New-Pass-1").status_code == 200


def test_password_hashing_rules():
    hashed = hash_password(PASSWORD)
    assert hashed != PASSWORD and hashed.startswith("$2")
    assert verify_password(PASSWORD, hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password(PASSWORD, None)
    with pytest.raises(ValueError):
        hash_password("é" * 40)  # 80 bytes > bcrypt's 72-byte limit


# ---------------------------------------------------------------- configuration

def test_production_requires_rs256_key_files():
    production = replace(get_settings(), environment="production", jwt_algorithm="RS256",
                         jwt_private_key_path=None, jwt_public_key_path=None)
    with pytest.raises(RuntimeError):
        production.validate()


def test_unsupported_algorithm_is_rejected():
    with pytest.raises(RuntimeError):
        replace(get_settings(), jwt_algorithm="none").validate()

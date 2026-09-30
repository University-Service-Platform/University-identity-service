"""Forgot password: emailed one-time link, then a new password."""
import json
import re
from dataclasses import replace
from datetime import timedelta

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.core.time import utc_now
from app.integrations.email_sender import EmailDeliveryError, EmailSender, get_email_sender
from app.main import app
from app.models.audit_log import AuditLog
from app.models.password_reset import PasswordResetToken
from app.models.user import AccountStatus
from app.services import password_reset_service
from tests.helpers import create_user

RESET_URL = "https://frontend.example/reset-password"
PASSWORD = "Old-Pass-123"


class FakeSender:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, text, html):
        self.sent.append({"to": to, "subject": subject, "text": text, "html": html})


@pytest.fixture
def outbox(monkeypatch):
    sender = FakeSender()
    app.dependency_overrides[get_email_sender] = lambda: sender
    monkeypatch.setattr(password_reset_service, "get_settings",
                        lambda: replace(get_settings(), password_reset_url=RESET_URL))
    yield sender.sent
    app.dependency_overrides.pop(get_email_sender, None)


@pytest.fixture
def user(db_session):
    account = create_user(db_session, "usr-reset-01", role="STUDENT")
    account.password_hash = hash_password(PASSWORD)
    db_session.commit()
    return account


def token_from(email) -> str:
    return re.search(r"token=([\w-]+)", email["text"]).group(1)


def login(client, username, password):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_reset_by_email_link(client, db_session, user, outbox):
    response = client.post("/api/v1/auth/forgot-password", json={"email": user.email.upper()})
    assert response.status_code == 200
    assert len(outbox) == 1 and outbox[0]["to"] == user.email
    assert f"{RESET_URL}?token=" in outbox[0]["text"] and f"{RESET_URL}?token=" in outbox[0]["html"]

    token = token_from(outbox[0])
    stored = db_session.query(PasswordResetToken).one()
    assert stored.token_hash != token and len(stored.token_hash) == 64   # only the hash is kept

    response = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "New-Pass-456"})
    assert response.status_code == 200
    assert login(client, user.university_id, "New-Pass-456").status_code == 200
    assert login(client, user.university_id, PASSWORD).status_code == 401

    actions = [a for (a,) in db_session.query(AuditLog.action).filter(AuditLog.target_id == user.id)]
    assert "PASSWORD_RESET_REQUESTED" in actions and "PASSWORD_RESET_COMPLETED" in actions


def test_the_answer_never_shows_whether_an_account_exists(client, db_session, user, outbox):
    known = client.post("/api/v1/auth/forgot-password", json={"email": user.email}).json()
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@university.example"}).json()
    assert known == unknown
    assert len(outbox) == 1


def test_university_id_is_accepted(client, db_session, user, outbox):
    client.post("/api/v1/auth/forgot-password", json={"email": user.university_id})
    assert len(outbox) == 1


def test_inactive_accounts_get_no_link(client, db_session, user, outbox):
    user.status = AccountStatus.INACTIVE
    db_session.commit()
    assert client.post("/api/v1/auth/forgot-password", json={"email": user.email}).status_code == 200
    assert outbox == []


def test_shared_demo_accounts_get_no_link(client, db_session, outbox):
    demo = create_user(db_session, "usr-student-001", role="STUDENT")
    assert client.post("/api/v1/auth/forgot-password", json={"email": demo.email}).status_code == 200
    assert outbox == []


def test_link_works_once(client, db_session, user, outbox):
    client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    token = token_from(outbox[0])
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "New-Pass-456"}).status_code == 200
    again = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "Other-Pass-789"})
    assert again.status_code == 400 and again.json()["error"]["code"] == "INVALID_RESET_TOKEN"


def test_a_new_link_replaces_the_old_one(client, db_session, user, outbox):
    client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    old, new = token_from(outbox[0]), token_from(outbox[1])
    assert client.post("/api/v1/auth/reset-password", json={"token": old, "new_password": "New-Pass-456"}).status_code == 400
    assert client.post("/api/v1/auth/reset-password", json={"token": new, "new_password": "New-Pass-456"}).status_code == 200


def test_expired_link_is_refused(client, db_session, user, outbox):
    client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    record = db_session.query(PasswordResetToken).one()
    record.expires_at = utc_now() - timedelta(seconds=1)
    db_session.commit()
    response = client.post("/api/v1/auth/reset-password", json={"token": token_from(outbox[0]), "new_password": "New-Pass-456"})
    assert response.status_code == 400


def test_requests_are_rate_limited(client, db_session, user, outbox):
    for _ in range(5):
        assert client.post("/api/v1/auth/forgot-password", json={"email": user.email}).status_code == 200
    assert len(outbox) == password_reset_service.MAX_REQUESTS_PER_WINDOW


def test_unknown_token_and_weak_password_are_refused(client, db_session, outbox):
    assert client.post("/api/v1/auth/reset-password",
                       json={"token": "x" * 43, "new_password": "New-Pass-456"}).status_code == 400
    assert client.post("/api/v1/auth/reset-password",
                       json={"token": "x" * 43, "new_password": "short"}).status_code == 422


def test_no_email_provider_still_answers(client, db_session, user, monkeypatch):
    app.dependency_overrides[get_email_sender] = lambda: None
    monkeypatch.setattr(password_reset_service, "get_settings",
                        lambda: replace(get_settings(), password_reset_url=RESET_URL))
    try:
        assert client.post("/api/v1/auth/forgot-password", json={"email": user.email}).status_code == 200
    finally:
        app.dependency_overrides.pop(get_email_sender, None)


def test_endpoints_need_no_token(client, db_session, outbox):
    # Called by signed-out users: no Authorization header at all
    assert client.post("/api/v1/auth/forgot-password", json={"email": "a@b.example"}).status_code == 200


# ---------------------------------------------------------------- email providers

def capture(status_code=201):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status_code, json={"messageId": "m-1"})
    return requests, httpx.MockTransport(handler)


def test_brevo_request():
    requests, transport = capture()
    EmailSender("brevo", "key-1", "Uni Services <noreply@gmail.com>", transport=transport).send(
        "to@example.com", "Subject", "text body", "<p>html</p>")
    request = requests[0]
    assert str(request.url) == "https://api.brevo.com/v3/smtp/email"
    assert request.headers["api-key"] == "key-1"
    assert json.loads(request.content) == {
        "sender": {"name": "Uni Services", "email": "noreply@gmail.com"}, "to": [{"email": "to@example.com"}],
        "subject": "Subject", "textContent": "text body", "htmlContent": "<p>html</p>"}


def test_resend_request():
    requests, transport = capture(200)
    EmailSender("resend", "key-2", "noreply@uni.example", transport=transport).send("to@example.com", "S", "t", "h")
    assert requests[0].headers["Authorization"] == "Bearer key-2"
    assert json.loads(requests[0].content)["from"] == "University Services Platform <noreply@uni.example>"


def test_provider_refusal_raises():
    _, transport = capture(401)
    with pytest.raises(EmailDeliveryError):
        EmailSender("brevo", "bad", "a@b.example", transport=transport).send("to@example.com", "S", "t", "h")


# ---------------------------------------------------------------- configuration

def settings(**overrides) -> Settings:
    return replace(get_settings(), **overrides)


def test_provider_needs_its_settings():
    with pytest.raises(RuntimeError, match="PASSWORD_RESET_URL"):
        settings(email_provider="brevo", email_api_key="k", email_from="a@b.example").validate()
    with pytest.raises(RuntimeError, match="EMAIL_API_KEY"):
        settings(email_provider="brevo", password_reset_url=RESET_URL).validate()
    with pytest.raises(RuntimeError, match="EMAIL_PROVIDER"):
        settings(email_provider="smtp").validate()
    settings(email_provider="brevo", email_api_key="k", email_from="a@b.example",
             password_reset_url=RESET_URL).validate()


def test_log_provider_is_refused_in_production():
    with pytest.raises(RuntimeError, match="EMAIL_PROVIDER=log"):
        settings(environment="production", email_provider="log", password_reset_url=RESET_URL,
                 jwt_private_key_path="/k", jwt_public_key_path="/p").validate()

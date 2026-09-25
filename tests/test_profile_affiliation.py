"""
Profile enrichment with the Directory Service affiliation. The Directory Service is
stubbed with httpx.MockTransport; the profile must stay available when it fails.
"""
import httpx
import pytest

from app.integrations.directory_client import DirectoryClient, get_directory_client
from app.main import app
from tests.helpers import auth_header, create_user

AFFILIATION = {
    "success": True,
    "data": {
        "id": "aff-1", "user_id": "usr-prof-student", "department_id": "dep-cs",
        "department_name": "Computer Science", "department_code": "CS", "faculty_id": "fac-sci",
        "faculty_name": "Faculty of Science", "faculty_code": "SCI", "created_at": "2026-09-01T10:00:00",
    },
}


def use_directory(handler):
    app.dependency_overrides[get_directory_client] = lambda: DirectoryClient(
        "http://directory.test", 1.0, transport=httpx.MockTransport(handler)
    )


@pytest.fixture
def student(db_session):
    return create_user(db_session, "usr-prof-student", role="STUDENT")


def get_profile(client, user_id, as_user):
    return client.get(f"/api/v1/users/{user_id}", headers=auth_header(as_user))


def test_profile_includes_directory_affiliation(client, student):
    use_directory(lambda request: httpx.Response(200, json=AFFILIATION))

    data = get_profile(client, student.id, student.id).json()["data"]
    assert data["affiliation_status"] == "AVAILABLE"
    assert data["affiliation"] == {
        "department_id": "dep-cs", "department_name": "Computer Science",
        "faculty_id": "fac-sci", "faculty_name": "Faculty of Science",
    }


def test_profile_without_affiliation(client, student):
    use_directory(lambda request: httpx.Response(
        404, json={"success": False, "error": {"code": "AFFILIATION_NOT_FOUND", "message": "..."}}))

    data = get_profile(client, student.id, student.id).json()["data"]
    assert data["affiliation_status"] == "NONE"
    assert data["affiliation"] is None


@pytest.mark.parametrize("handler", [
    lambda request: (_ for _ in ()).throw(httpx.ConnectError("refused")),
    lambda request: httpx.Response(503, json={}),
    lambda request: httpx.Response(200, text="not json"),
])
def test_profile_survives_directory_failures(client, student, handler):
    use_directory(handler)

    response = get_profile(client, student.id, student.id)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user_id"] == student.id
    assert data["affiliation_status"] == "UNAVAILABLE"
    assert data["affiliation"] is None


def test_profile_reports_not_configured_without_directory_url(client, student):
    app.dependency_overrides[get_directory_client] = lambda: DirectoryClient(None, 1.0)
    data = get_profile(client, student.id, student.id).json()["data"]
    assert data["affiliation_status"] == "NOT_CONFIGURED"


def test_directory_not_called_when_profile_access_is_forbidden(client, db_session, student):
    calls = []
    use_directory(lambda request: calls.append(request) or httpx.Response(200, json=AFFILIATION))
    other = create_user(db_session, "usr-prof-other", role="STUDENT")

    response = get_profile(client, other.id, student.id)
    assert response.status_code == 403
    assert calls == []

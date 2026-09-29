"""
Responsibility-aware eligibility tests. The Directory Service is stubbed with
httpx.MockTransport via a FastAPI dependency override; no real network calls.
"""
import httpx
import pytest

from app.integrations.directory_client import DirectoryClient, get_directory_client
from app.main import app
from app.models.user import AccountStatus
from tests.helpers import auth_header, create_user

URL = "/api/v1/validation/users/{}/eligibility"

AFFILIATION = {
    "success": True,
    "data": {
        "id": "aff-1", "user_id": "usr-elig-student", "department_id": "dep-cs",
        "department_name": "Computer Science", "department_code": "CS", "faculty_id": "fac-sci",
        "faculty_name": "Faculty of Science", "faculty_code": "SCI", "created_at": "2026-09-01T10:00:00",
    },
}

AFFILIATION_VALIDATION_PATH = "/api/v1/validation/users/usr-elig-student/affiliation"
PRIMARY_AFFILIATION_PATH = "/api/v1/affiliations/users/usr-elig-student"


def affiliation_matches(*departments):
    """Body of the Directory's affiliation validation endpoint: one entry per matching affiliation."""
    return {
        "success": True,
        "data": {
            "user_id": "usr-elig-student", "is_valid": True,
            "affiliations": [{
                "affiliation_id": f"aff-{code.lower()}",
                "department": {"id": f"dep-{code.lower()}", "code": code, "name": name},
                "faculty": {"id": "fac-sci", "code": "SCI", "name": "Faculty of Science"},
            } for code, name in departments],
        },
    }


RESPONSIBILITY = {
    "success": True,
    "data": {
        "user_id": "usr-elig-staff", "is_valid": True,
        "responsibilities": [{
            "responsibility_id": "rsp-1", "user_id": "usr-elig-staff", "service_unit_id": "su-it",
            "service_unit_name": "IT Services", "role_title": "Service Desk Lead", "status": "ACTIVE",
        }],
    },
}


def error(code):
    return {"success": False, "error": {"code": code, "message": "..."}}


class DirectoryStub:
    """Records requests and answers with a configurable response per path (or raises)."""

    def __init__(self):
        self.requests = []
        self.status_code = 200
        self.body = None
        self.routes = {}
        self.exception = None

    def respond(self, status_code, body):
        """Default answer for any path."""
        self.status_code, self.body = status_code, body

    def respond_to(self, path, status_code, body):
        self.routes[path] = (status_code, body)

    def handler(self, request):
        self.requests.append(request)
        if self.exception:
            raise self.exception
        status_code, body = self.routes.get(request.url.path, (self.status_code, self.body))
        return httpx.Response(status_code, json=body)


@pytest.fixture
def directory(client):
    stub = DirectoryStub()
    app.dependency_overrides[get_directory_client] = lambda: DirectoryClient(
        "http://directory.test", 1.0, transport=httpx.MockTransport(stub.handler)
    )
    return stub


@pytest.fixture
def caller(db_session):
    return create_user(db_session, "usr-elig-caller", role="STAFF")


def check(client, user_id, **params):
    return client.get(URL.format(user_id), params=params, headers=auth_header("usr-elig-caller"))


# ---------------------------------------------------------------- identity-only checks

def test_role_only_check_does_not_call_directory(client, db_session, directory, caller):
    create_user(db_session, "usr-elig-rm", role="RESOURCE_MANAGER")

    data = check(client, "usr-elig-rm", required_role="resource_manager").json()["data"]
    assert data["eligible"] is True
    assert data["reasons"] == []
    assert data["message"] == "User is eligible."
    assert data["checks"]["role_held"] is True
    assert directory.requests == []


def test_missing_role_is_reported(client, db_session, directory, caller):
    create_user(db_session, "usr-elig-student", role="STUDENT")
    data = check(client, "usr-elig-student", required_role="EVENT_ORGANIZER").json()["data"]
    assert data["eligible"] is False
    assert data["reasons"] == ["ROLE_NOT_HELD"]


def test_inactive_user_is_ineligible_without_consulting_directory(client, db_session, directory, caller):
    create_user(db_session, "usr-elig-inactive", role="STAFF", status=AccountStatus.INACTIVE)
    directory.exception = httpx.ConnectError("directory down")  # must not matter

    response = check(client, "usr-elig-inactive", relationship="RESPONSIBILITY", service_unit_id="su-it")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["eligible"] is False
    assert data["reasons"] == ["ACCOUNT_INACTIVE"]
    assert data["checks"]["relationship_satisfied"] is None
    assert directory.requests == []


# ---------------------------------------------------------------- responsibility

def test_active_responsibility_makes_staff_eligible(client, db_session, directory, caller):
    create_user(db_session, "usr-elig-staff", role="SERVICE_DESK_OFFICER")
    directory.respond(200, RESPONSIBILITY)

    data = check(client, "usr-elig-staff", required_role="SERVICE_DESK_OFFICER",
                 relationship="RESPONSIBILITY", service_unit_id="su-it").json()["data"]
    assert data["eligible"] is True
    assert data["checks"]["relationship_satisfied"] is True
    assert data["matched_responsibilities"][0]["role_title"] == "Service Desk Lead"
    assert dict(directory.requests[0].url.params) == {"service_unit_id": "su-it"}


def test_same_role_without_responsibility_is_not_eligible(client, db_session, directory, caller):
    """Key business rule: not every staff member with the same role has the same permissions."""
    create_user(db_session, "usr-elig-other", role="SERVICE_DESK_OFFICER")
    directory.respond(404, error("RESPONSIBILITY_NOT_FOUND"))

    data = check(client, "usr-elig-other", required_role="SERVICE_DESK_OFFICER",
                 relationship="RESPONSIBILITY", service_unit_id="su-it").json()["data"]
    assert data["eligible"] is False
    assert data["reasons"] == ["NO_MATCHING_RESPONSIBILITY"]
    assert data["checks"]["role_held"] is True


def test_inactive_responsibility_is_reported(client, db_session, directory, caller):
    create_user(db_session, "usr-elig-staff2", role="STAFF")
    directory.respond(403, error("RESPONSIBILITY_INACTIVE"))

    data = check(client, "usr-elig-staff2", relationship="RESPONSIBILITY", department_id="dep-cs").json()["data"]
    assert data["reasons"] == ["RESPONSIBILITY_INACTIVE"]


# ---------------------------------------------------------------- affiliation

@pytest.mark.parametrize("params", [
    {"department_id": "dep-cs"},
    {"department_id": "cs"},                          # department code; the Directory matches codes case-insensitively
    {"department_id": "dep-cs", "faculty_id": "SCI"},
])
def test_matching_affiliation_is_eligible(client, db_session, directory, caller, params):
    create_user(db_session, "usr-elig-student", role="STUDENT")
    directory.respond_to(AFFILIATION_VALIDATION_PATH, 200, affiliation_matches(("CS", "Computer Science")))

    data = check(client, "usr-elig-student", relationship="AFFILIATION", **params).json()["data"]
    assert data["eligible"] is True
    assert data["affiliation"]["department_name"] == "Computer Science"
    # The unit is matched by the Directory, which checks all of the user's affiliations
    assert directory.requests[0].url.path == AFFILIATION_VALIDATION_PATH
    assert dict(directory.requests[0].url.params) == params
    assert len(directory.requests) == 1


def test_student_in_two_departments_is_eligible_for_the_second_one(client, db_session, directory, caller):
    """Regression: only the primary affiliation used to be checked, so a second department failed."""
    create_user(db_session, "usr-elig-student", role="STUDENT")
    directory.respond_to(PRIMARY_AFFILIATION_PATH, 200, AFFILIATION)            # primary: Computer Science
    directory.respond_to(AFFILIATION_VALIDATION_PATH, 200, affiliation_matches(("MATH", "Mathematics")))

    data = check(client, "usr-elig-student", required_role="STUDENT",
                 relationship="AFFILIATION", department_id="MATH").json()["data"]
    assert data["eligible"] is True
    assert data["reasons"] == []
    assert data["affiliation"]["department_name"] == "Mathematics"


def test_affiliation_with_other_department_is_mismatch(client, db_session, directory, caller):
    create_user(db_session, "usr-elig-student", role="STUDENT")
    directory.respond_to(AFFILIATION_VALIDATION_PATH, 404, error("AFFILIATION_NOT_FOUND"))
    directory.respond_to(PRIMARY_AFFILIATION_PATH, 200, AFFILIATION)

    data = check(client, "usr-elig-student", relationship="AFFILIATION", department_id="dep-math").json()["data"]
    assert data["eligible"] is False
    assert data["reasons"] == ["AFFILIATION_MISMATCH"]
    assert data["affiliation"]["department_name"] == "Computer Science"   # where the user actually belongs


@pytest.mark.parametrize("status_code,code", [
    (404, "DEPARTMENT_NOT_FOUND"),
    (400, "INVALID_ORGANIZATIONAL_RELATIONSHIP"),
])
def test_unknown_or_inconsistent_unit_is_mismatch_not_error(client, db_session, directory, caller,
                                                            status_code, code):
    create_user(db_session, "usr-elig-student", role="STUDENT")
    directory.respond_to(AFFILIATION_VALIDATION_PATH, status_code, error(code))
    directory.respond_to(PRIMARY_AFFILIATION_PATH, 200, AFFILIATION)

    response = check(client, "usr-elig-student", relationship="AFFILIATION", department_id="NOPE")
    assert response.status_code == 200
    assert response.json()["data"]["reasons"] == ["AFFILIATION_MISMATCH"]


def test_user_without_affiliation(client, db_session, directory, caller):
    create_user(db_session, "usr-elig-student", role="STUDENT")
    directory.respond(404, error("AFFILIATION_NOT_FOUND"))

    data = check(client, "usr-elig-student", relationship="AFFILIATION", department_id="dep-cs").json()["data"]
    assert data["reasons"] == ["NO_AFFILIATION"]
    assert data["affiliation"] is None


# ---------------------------------------------------------------- dependency failures

@pytest.mark.parametrize("failure", ["timeout", "connection", "server_error"])
def test_directory_unavailable_returns_503(client, db_session, directory, caller, failure):
    create_user(db_session, "usr-elig-staff", role="STAFF")
    if failure == "timeout":
        directory.exception = httpx.ReadTimeout("slow")
    elif failure == "connection":
        directory.exception = httpx.ConnectError("refused")
    else:
        directory.respond(500, error("INTERNAL_SERVER_ERROR"))

    response = check(client, "usr-elig-staff", relationship="RESPONSIBILITY", service_unit_id="su-it")
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert "refused" not in response.text and "slow" not in response.text


def test_invalid_directory_payload_returns_502(client, db_session, directory, caller):
    create_user(db_session, "usr-elig-staff", role="STAFF")
    directory.respond(200, {"unexpected": True})

    response = check(client, "usr-elig-staff", relationship="RESPONSIBILITY", service_unit_id="su-it")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "DEPENDENCY_ERROR"


def test_unconfigured_directory_returns_503(client, db_session, caller):
    create_user(db_session, "usr-elig-staff", role="STAFF")
    app.dependency_overrides[get_directory_client] = lambda: DirectoryClient(None, 1.0)

    response = check(client, "usr-elig-staff", relationship="AFFILIATION", department_id="dep-cs")
    assert response.status_code == 503


# ---------------------------------------------------------------- request handling

def test_caller_token_is_forwarded_to_directory(client, db_session, directory, caller):
    create_user(db_session, "usr-elig-staff", role="STAFF")
    directory.respond(200, RESPONSIBILITY)

    check(client, "usr-elig-staff", relationship="RESPONSIBILITY", service_unit_id="su-it")
    assert directory.requests[0].headers["Authorization"].startswith("Bearer ")


@pytest.mark.parametrize("params", [
    {"department_id": "dep-cs"},                                        # unit without relationship
    {"relationship": "RESPONSIBILITY"},                                 # relationship without unit
    {"relationship": "AFFILIATION", "service_unit_id": "su-it"},        # affiliations have no service unit
    {"relationship": "SOMETHING", "department_id": "dep-cs"},           # unknown relationship
])
def test_invalid_query_combinations_return_422(client, db_session, directory, caller, params):
    create_user(db_session, "usr-elig-staff", role="STAFF")
    response = check(client, "usr-elig-staff", **params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_user_returns_404(client, db_session, directory, caller):
    response = check(client, "usr-nobody-here", required_role="STAFF")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_eligibility_requires_authentication(client, directory):
    response = client.get(URL.format("usr-elig-staff"))
    assert response.status_code == 401

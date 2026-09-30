"""
Directory Service client tests. The Directory Service is replaced by httpx.MockTransport;
payloads mirror the Directory Service's documented response schemas.
"""
import httpx
import pytest

from app.integrations.directory_client import (
    DirectoryClient,
    DirectoryServiceError,
    DirectoryServiceUnavailable,
    ResponsibilityOutcome,
)

BASE_URL = "http://directory.test"

RESPONSIBILITY_OK = {
    "success": True,
    "data": {
        "user_id": "usr-staff-001",
        "is_valid": True,
        "responsibilities": [{
            "responsibility_id": "rsp-1",
            "user_id": "usr-staff-001",
            "service_unit_id": "su-it",
            "service_unit_name": "IT Services",
            "department_id": None,
            "department_name": None,
            "faculty_id": None,
            "faculty_name": None,
            "role_title": "Service Desk Lead",
            "status": "ACTIVE",
        }],
    },
}

AFFILIATION_OK = {
    "success": True,
    "data": {
        "id": "aff-1",
        "user_id": "usr-student-001",
        "department_id": "dep-cs",
        "department_name": "Computer Science",
        "department_code": "CS",
        "faculty_id": "fac-sci",
        "faculty_name": "Faculty of Science",
        "faculty_code": "SCI",
        "created_at": "2026-09-01T10:00:00",
        "updated_at": None,
    },
}


# GET /api/v1/validation/users/{user_id}/affiliation: every matching affiliation of the user
AFFILIATION_VALIDATION_OK = {
    "success": True,
    "data": {
        "user_id": "usr-student-001",
        "is_valid": True,
        "affiliations": [{
            "affiliation_id": "aff-2",
            "department": {"id": "dept-math-1a2b3c", "code": "MATH", "name": "Department of Mathematics"},
            "faculty": {"id": "fac-fsc-4d5e6f", "code": "FSC", "name": "Faculty of Science"},
        }],
    },
}


def error(code: str) -> dict:
    return {"success": False, "error": {"code": code, "message": "..."}}


def client_returning(status_code: int, json_body=None, text_body=None, seen=None) -> DirectoryClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if text_body is not None:
            return httpx.Response(status_code, text=text_body)
        return httpx.Response(status_code, json=json_body)
    return DirectoryClient(BASE_URL, 1.0, transport=httpx.MockTransport(handler))


def client_raising(exc: Exception) -> DirectoryClient:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc
    return DirectoryClient(BASE_URL, 1.0, transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------- responsibilities

def test_active_responsibility_is_parsed_and_filters_are_sent():
    seen = []
    result = client_returning(200, RESPONSIBILITY_OK, seen=seen).get_user_responsibilities(
        "usr-staff-001", service_unit_id="su-it"
    )
    assert result.outcome is ResponsibilityOutcome.ACTIVE
    assert result.responsibilities[0].role_title == "Service Desk Lead"
    assert seen[0].url.path == "/api/v1/validation/users/usr-staff-001/responsibilities"
    assert dict(seen[0].url.params) == {"service_unit_id": "su-it"}


def test_no_matching_responsibility_maps_to_none():
    result = client_returning(404, error("RESPONSIBILITY_NOT_FOUND")).get_user_responsibilities("usr-x-001")
    assert result.outcome is ResponsibilityOutcome.NONE


def test_inactive_responsibility_maps_to_inactive():
    result = client_returning(403, error("RESPONSIBILITY_INACTIVE")).get_user_responsibilities("usr-x-001")
    assert result.outcome is ResponsibilityOutcome.INACTIVE


# ---------------------------------------------------------------- affiliation

def test_affiliation_is_parsed():
    affiliation = client_returning(200, AFFILIATION_OK).get_user_affiliation("usr-student-001")
    assert affiliation.affiliation_id == "aff-1"
    assert affiliation.department_code == "CS"
    assert affiliation.faculty_name == "Faculty of Science"


def test_missing_affiliation_returns_none():
    assert client_returning(404, error("AFFILIATION_NOT_FOUND")).get_user_affiliation("usr-x-001") is None


def test_primary_affiliation_uses_the_versioned_path():
    seen = []
    client_returning(200, AFFILIATION_OK, seen=seen).get_user_affiliation("usr-student-001")
    assert seen[0].url.path == "/api/v1/affiliations/users/usr-student-001"


# ---------------------------------------------------------------- affiliation validation (all affiliations)

def test_matching_affiliations_are_parsed_and_filters_are_sent():
    seen = []
    matches = client_returning(200, AFFILIATION_VALIDATION_OK, seen=seen).find_user_affiliations(
        "usr-student-001", department_id="MATH", faculty_id="FSC"
    )
    assert seen[0].url.path == "/api/v1/validation/users/usr-student-001/affiliation"
    assert dict(seen[0].url.params) == {"department_id": "MATH", "faculty_id": "FSC"}
    assert len(matches) == 1
    assert matches[0].affiliation_id == "aff-2"
    assert matches[0].department_id == "dept-math-1a2b3c"
    assert matches[0].department_code == "MATH"
    assert matches[0].faculty_name == "Faculty of Science"


@pytest.mark.parametrize("status_code,code", [
    (404, "AFFILIATION_NOT_FOUND"),               # user has no affiliation with that unit
    (404, "DEPARTMENT_NOT_FOUND"),                # requested department does not exist
    (404, "FACULTY_NOT_FOUND"),                   # requested faculty does not exist
    (400, "INVALID_ORGANIZATIONAL_RELATIONSHIP"), # department is not in that faculty
])
def test_no_matching_affiliation_returns_empty_list(status_code, code):
    matches = client_returning(status_code, error(code)).find_user_affiliations("usr-x-001", department_id="CS")
    assert matches == []


@pytest.mark.parametrize("status_code,body", [
    (200, {"success": True, "data": {"user_id": "usr-x-001", "affiliations": [{"affiliation_id": "aff-1"}]}}),
    (200, {"success": True, "data": {"user_id": "usr-x-001"}}),       # affiliations missing
    (404, error("SOMETHING_ELSE")),
])
def test_unexpected_affiliation_validation_answers_raise_directory_error(status_code, body):
    with pytest.raises(DirectoryServiceError):
        client_returning(status_code, body).find_user_affiliations("usr-x-001", department_id="CS")


# ---------------------------------------------------------------- failure handling

@pytest.mark.parametrize("exc", [
    httpx.ReadTimeout("timed out"),
    httpx.ConnectTimeout("timed out"),
    httpx.ConnectError("connection refused"),
])
def test_timeouts_and_connection_failures_are_unavailable(exc):
    with pytest.raises(DirectoryServiceUnavailable):
        client_raising(exc).get_user_responsibilities("usr-x-001")


@pytest.mark.parametrize("status_code", [500, 502, 503])
def test_server_errors_are_unavailable(status_code):
    with pytest.raises(DirectoryServiceUnavailable):
        client_returning(status_code, error("INTERNAL_SERVER_ERROR")).get_user_affiliation("usr-x-001")


def test_unconfigured_client_is_unavailable():
    with pytest.raises(DirectoryServiceUnavailable):
        DirectoryClient(None, 1.0).get_user_affiliation("usr-x-001")


@pytest.mark.parametrize("status_code,body,text", [
    (200, None, "<html>not json</html>"),                              # not JSON
    (200, {"success": True, "data": {"responsibilities": [{"x": 1}]}}, None),  # wrong record shape
    (200, {"unexpected": "envelope"}, None),                           # missing data
    (400, error("INVALID_IDENTIFIER_FORMAT"), None),                   # undocumented status for us
    (404, error("SOMETHING_ELSE"), None),                              # unknown 404 code
])
def test_contract_violations_raise_directory_error(status_code, body, text):
    with pytest.raises(DirectoryServiceError):
        client_returning(status_code, body, text).get_user_responsibilities("usr-x-001")


def test_invalid_affiliation_payload_raises_directory_error():
    broken = {"success": True, "data": {"id": "aff-1"}}  # department/faculty missing
    with pytest.raises(DirectoryServiceError):
        client_returning(200, broken).get_user_affiliation("usr-x-001")


# ---------------------------------------------------------------- request details

def test_caller_authorization_is_forwarded():
    seen = []
    client = client_returning(200, AFFILIATION_OK, seen=seen).with_authorization("Bearer abc.def.ghi")
    client.get_user_affiliation("usr-student-001")
    assert seen[0].headers["Authorization"] == "Bearer abc.def.ghi"


def test_user_id_is_url_encoded():
    seen = []
    client_returning(404, error("AFFILIATION_NOT_FOUND"), seen=seen).get_user_affiliation("../admin")
    assert seen[0].url.raw_path == b"/api/v1/affiliations/users/..%2Fadmin"


# ---------------------------------------------------------------- unit id-or-code lookup

@pytest.mark.parametrize("kind,path,field", [
    ("department", "/api/v1/validation/departments/CS", "department_id"),
    ("faculty", "/api/v1/validation/faculties/CS", "faculty_id"),
    ("service_unit", "/api/v1/validation/service-units/CS", "unit_id"),
])
def test_unit_code_resolves_to_its_directory_id(kind, path, field):
    seen = []
    client = client_returning(200, {"success": True, "data": {field: "unit-cs-1a2b3c", "code": "CS"}}, seen=seen)
    assert client.resolve_unit_id(kind, "CS") == "unit-cs-1a2b3c"
    assert seen[0].url.path == path


@pytest.mark.parametrize("status_code,code", [
    (404, "DEPARTMENT_NOT_FOUND"), (404, "FACULTY_NOT_FOUND"), (404, "SERVICE_UNIT_NOT_FOUND"),
    (400, "INVALID_IDENTIFIER_FORMAT"), (400, "INVALID_ORGANIZATIONAL_RELATIONSHIP"),
])
def test_unknown_unit_resolves_to_none(status_code, code):
    assert client_returning(status_code, error(code)).resolve_unit_id("department", "NOPE") is None


@pytest.mark.parametrize("status_code,body", [
    (200, {"success": True, "data": {"code": "CS"}}),        # id missing
    (404, error("SOMETHING_ELSE")),
])
def test_unexpected_unit_lookup_answers_raise_directory_error(status_code, body):
    with pytest.raises(DirectoryServiceError):
        client_returning(status_code, body).resolve_unit_id("department", "CS")

"""
Consumer contract tests: each test plays a downstream team's service and uses ONLY the
fields of the published cross-service API contract. If a change breaks one of these tests,
it is a breaking change for that team and must be announced before release.

  Group 6 (reservations)      - may this user approve reservations for this department?
  Group 7 (work orders)       - is this user an active technician?
  Group 8 (events)            - may this student register for a department-only event?
"""
import httpx
import pytest

from app.integrations.directory_client import DirectoryClient, get_directory_client
from app.main import app
from app.models.user import AccountStatus, AccountType
from app.reference_data import ensure_reference_data
from tests.helpers import auth_header, create_user

SUCCESS_KEYS = {"success", "data"}
ERROR_KEYS = {"success", "error", "timestamp"}
VALIDATION_KEYS = {"user_id", "university_id", "name", "account_type", "status", "is_valid", "roles",
                   "is_authorized", "required_role_checked"}
ELIGIBILITY_KEYS = {"user_id", "university_id", "account_status", "roles", "eligible", "reasons", "message",
                    "checks", "matched_responsibilities", "affiliation"}


@pytest.fixture
def platform(db_session):
    ensure_reference_data(db_session)
    create_user(db_session, "usr-g6-manager", role="RESOURCE_MANAGER")
    create_user(db_session, "usr-g7-tech", role="TECHNICIAN")
    create_user(db_session, "usr-g7-tech-off", role="TECHNICIAN", status=AccountStatus.INACTIVE)
    create_user(db_session, "usr-g8-student", role="STUDENT", account_type=AccountType.STUDENT)
    return db_session


def stub_directory(responses):
    """responses: URL path -> (status, json)"""
    def handler(request: httpx.Request) -> httpx.Response:
        status_code, body = responses[request.url.path]
        return httpx.Response(status_code, json=body)
    app.dependency_overrides[get_directory_client] = lambda: DirectoryClient(
        "http://directory.test", 1.0, transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------- Group 6

def group6_can_approve_reservation(client, token_headers, user_id, department_id):
    """Reservation-service rule: approver must be a RESOURCE_MANAGER responsible for the resource's department."""
    response = client.get(f"/api/v1/validation/users/{user_id}/eligibility", headers=token_headers, params={
        "required_role": "RESOURCE_MANAGER", "relationship": "RESPONSIBILITY", "department_id": department_id,
    })
    if response.status_code != 200:
        return False, response.json()["error"]["code"]
    data = response.json()["data"]
    return data["eligible"], data["message"]


def test_group6_resource_manager_responsible_for_department_may_approve(client, platform):
    stub_directory({"/validation/users/usr-g6-manager/responsibilities": (200, {"success": True, "data": {
        "user_id": "usr-g6-manager", "is_valid": True, "responsibilities": [{
            "responsibility_id": "rsp-9", "user_id": "usr-g6-manager", "department_id": "dep-cs",
            "department_name": "Computer Science", "role_title": "Lab Resource Manager", "status": "ACTIVE"}]}})})

    allowed, message = group6_can_approve_reservation(client, auth_header("usr-g6-manager"), "usr-g6-manager", "dep-cs")
    assert allowed is True
    assert message == "User is eligible."


def test_group6_manager_of_another_department_may_not_approve(client, platform):
    stub_directory({"/validation/users/usr-g6-manager/responsibilities": (404, {
        "success": False, "error": {"code": "RESPONSIBILITY_NOT_FOUND", "message": "..."}})})

    allowed, message = group6_can_approve_reservation(client, auth_header("usr-g6-manager"), "usr-g6-manager", "dep-math")
    assert allowed is False
    assert message == "User has no responsibility for the requested organizational unit."


def test_group6_unknown_user_gets_documented_404(client, platform):
    allowed, code = group6_can_approve_reservation(client, auth_header("usr-g6-manager"), "usr-ghost-000", "dep-cs")
    assert (allowed, code) == (False, "USER_NOT_FOUND")


# ---------------------------------------------------------------- Group 7

def group7_is_active_technician(client, token_headers, user_id):
    response = client.get(f"/api/v1/validation/users/{user_id}", headers=token_headers,
                          params={"required_role": "TECHNICIAN", "require_active": "true"})
    if response.status_code == 403:
        return False
    data = response.json()["data"]
    return data["is_valid"] and data["is_authorized"]


def test_group7_active_technician_is_assignable(client, platform):
    assert group7_is_active_technician(client, auth_header("usr-g6-manager"), "usr-g7-tech") is True


def test_group7_inactive_technician_is_not_assignable(client, platform):
    assert group7_is_active_technician(client, auth_header("usr-g6-manager"), "usr-g7-tech-off") is False


def test_group7_student_is_not_a_technician(client, platform):
    assert group7_is_active_technician(client, auth_header("usr-g6-manager"), "usr-g8-student") is False


# ---------------------------------------------------------------- Group 8

def test_group8_department_only_event_registration(client, platform):
    stub_directory({"/affiliations/users/usr-g8-student": (200, {"success": True, "data": {
        "id": "aff-3", "user_id": "usr-g8-student", "department_id": "dep-cs", "department_name": "Computer Science",
        "department_code": "CS", "faculty_id": "fac-sci", "faculty_name": "Faculty of Science",
        "faculty_code": "SCI", "created_at": "2026-09-01T10:00:00"}})})
    headers = auth_header("usr-g8-student")
    url = "/api/v1/validation/users/usr-g8-student/eligibility"

    same_department = client.get(url, headers=headers, params={
        "required_role": "STUDENT", "relationship": "AFFILIATION", "department_id": "CS"}).json()["data"]
    other_department = client.get(url, headers=headers, params={
        "required_role": "STUDENT", "relationship": "AFFILIATION", "department_id": "MATH"}).json()["data"]

    assert same_department["eligible"] is True
    assert other_department["eligible"] is False
    # Group 8 must show ineligible users a clear explanation
    assert other_department["message"] == "User is not affiliated with the requested department/faculty."


# ---------------------------------------------------------------- response shapes

def test_documented_response_shapes_are_stable(client, platform):
    headers = auth_header("usr-g6-manager")

    validation = client.get("/api/v1/validation/users/usr-g7-tech", headers=headers).json()
    assert set(validation) == SUCCESS_KEYS
    assert set(validation["data"]) == VALIDATION_KEYS

    eligibility = client.get("/api/v1/validation/users/usr-g7-tech/eligibility", headers=headers,
                             params={"required_role": "TECHNICIAN"}).json()
    assert set(eligibility["data"]) == ELIGIBILITY_KEYS

    for status_code, response in [
        (401, client.get("/api/v1/validation/users/usr-g7-tech")),
        (403, client.get("/api/v1/audit-logs", headers=headers)),
        (404, client.get("/api/v1/validation/users/usr-ghost-000", headers=headers)),
    ]:
        assert response.status_code == status_code
        body = response.json()
        assert set(body) == ERROR_KEYS
        assert set(body["error"]) >= {"code", "message"}

"""
HTTP client for the University Directory Service (Group 5), which owns faculties,
departments, service units, user affiliations and service responsibilities.

The Identity Service never reads the Directory database; it only calls these
documented Directory endpoints:
    GET /validation/users/{user_id}/responsibilities
    GET /affiliations/users/{user_id}

Failures are translated into two exceptions so callers never leak downstream
details to their own clients:
    DirectoryServiceUnavailable - not configured, connection error, timeout or 5xx
    DirectoryServiceError       - unexpected status or malformed payload
"""
import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

logger = logging.getLogger("identity.integrations.directory")


class DirectoryServiceUnavailable(Exception):
    """The Directory Service could not be reached or failed (5xx)."""


class DirectoryServiceError(Exception):
    """The Directory Service answered with something outside its documented contract."""


class ResponsibilityRecord(BaseModel):
    responsibility_id: str
    service_unit_id: Optional[str] = None
    service_unit_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    faculty_id: Optional[str] = None
    faculty_name: Optional[str] = None
    role_title: str
    status: str


class ResponsibilityOutcome(str, Enum):
    ACTIVE = "ACTIVE"      # at least one matching active responsibility
    INACTIVE = "INACTIVE"  # matching responsibilities exist but none is active
    NONE = "NONE"          # no matching responsibility


class ResponsibilityCheck(BaseModel):
    outcome: ResponsibilityOutcome
    responsibilities: List[ResponsibilityRecord] = []


class Affiliation(BaseModel):
    affiliation_id: str
    department_id: str
    department_name: Optional[str] = None
    department_code: Optional[str] = None
    faculty_id: str
    faculty_name: Optional[str] = None
    faculty_code: Optional[str] = None


class DirectoryClient:
    def __init__(
        self,
        base_url: Optional[str],
        timeout_seconds: float,
        authorization: Optional[str] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.base_url = base_url.rstrip("/") if base_url else None
        self.timeout_seconds = timeout_seconds
        self.authorization = authorization
        self.transport = transport

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    def with_authorization(self, authorization: Optional[str]) -> "DirectoryClient":
        """Copy of this client that forwards the caller's Authorization header."""
        return DirectoryClient(self.base_url, self.timeout_seconds, authorization, self.transport)

    # ------------------------------------------------------------ public API

    def get_user_responsibilities(
        self,
        user_id: str,
        service_unit_id: Optional[str] = None,
        department_id: Optional[str] = None,
        faculty_id: Optional[str] = None,
    ) -> ResponsibilityCheck:
        params = {k: v for k, v in {
            "service_unit_id": service_unit_id,
            "department_id": department_id,
            "faculty_id": faculty_id,
        }.items() if v}
        response = self._get(f"/validation/users/{quote(user_id, safe='')}/responsibilities", params)

        if response.status_code == 200:
            data = self._data(response)
            try:
                records = [ResponsibilityRecord.model_validate(r) for r in data.get("responsibilities", [])]
            except (ValidationError, AttributeError, TypeError) as exc:
                raise self._contract_error("responsibility payload", response) from exc
            return ResponsibilityCheck(outcome=ResponsibilityOutcome.ACTIVE, responsibilities=records)

        error_code = self._error_code(response)
        if response.status_code == 404 and error_code == "RESPONSIBILITY_NOT_FOUND":
            return ResponsibilityCheck(outcome=ResponsibilityOutcome.NONE)
        if response.status_code == 403 and error_code == "RESPONSIBILITY_INACTIVE":
            return ResponsibilityCheck(outcome=ResponsibilityOutcome.INACTIVE)
        raise self._contract_error("responsibility status", response)

    def get_user_affiliation(self, user_id: str) -> Optional[Affiliation]:
        response = self._get(f"/affiliations/users/{quote(user_id, safe='')}")

        if response.status_code == 200:
            data = self._data(response)
            try:
                return Affiliation.model_validate({**data, "affiliation_id": data.get("id")})
            except (ValidationError, TypeError) as exc:
                raise self._contract_error("affiliation payload", response) from exc

        if response.status_code == 404 and self._error_code(response) == "AFFILIATION_NOT_FOUND":
            return None
        raise self._contract_error("affiliation status", response)

    # ------------------------------------------------------------ internals

    def _get(self, path: str, params: Optional[Dict[str, str]] = None) -> httpx.Response:
        if not self.is_configured:
            raise DirectoryServiceUnavailable("DIRECTORY_SERVICE_BASE_URL is not configured.")

        headers = {"Accept": "application/json"}
        if self.authorization:
            headers["Authorization"] = self.authorization

        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds,
                              transport=self.transport) as client:
                response = client.get(path, params=params, headers=headers)
        except httpx.TimeoutException as exc:
            logger.warning("Directory Service timed out on GET %s: %s", path, exc)
            raise DirectoryServiceUnavailable("Directory Service timed out.") from exc
        except httpx.HTTPError as exc:
            logger.warning("Directory Service unreachable on GET %s: %s", path, exc)
            raise DirectoryServiceUnavailable("Directory Service is unreachable.") from exc

        if response.status_code >= 500:
            logger.warning("Directory Service returned %s on GET %s", response.status_code, path)
            raise DirectoryServiceUnavailable(f"Directory Service returned {response.status_code}.")
        return response

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    def _data(self, response: httpx.Response) -> Dict[str, Any]:
        body = self._json(response)
        if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
            raise self._contract_error("response envelope", response)
        return body["data"]

    def _error_code(self, response: httpx.Response) -> Optional[str]:
        body = self._json(response)
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            return body["error"].get("code")
        return None

    @staticmethod
    def _contract_error(what: str, response: httpx.Response) -> DirectoryServiceError:
        logger.error("Unexpected Directory Service %s: HTTP %s %s",
                     what, response.status_code, response.text[:300])
        return DirectoryServiceError(f"Unexpected Directory Service {what} (HTTP {response.status_code}).")


def get_directory_client() -> DirectoryClient:
    """FastAPI dependency; tests override it with a client backed by a mock transport."""
    settings = get_settings()
    return DirectoryClient(settings.directory_service_base_url, settings.directory_service_timeout_seconds)

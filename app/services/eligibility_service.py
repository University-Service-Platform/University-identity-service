"""
Responsibility-aware eligibility: "the platform must not assume that every staff member
has the same permissions. Authorization must consider both system role and relevant
department or service responsibility."

Identity data (account status, roles) comes from the Identity DB. Organizational data
(affiliations, responsibilities) comes from the Directory Service API; it is never
copied into the Identity Service.
"""
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.integrations.directory_client import (
    DirectoryClient,
    DirectoryServiceError,
    DirectoryServiceUnavailable,
    ResponsibilityOutcome,
)
from app.models.user import AccountStatus
from app.repositories.user_repository import UserRepository
from app.schemas.directory import AffiliationSummary
from app.schemas.eligibility import (
    REASON_MESSAGES,
    EligibilityChecks,
    EligibilityData,
    EligibilityReason,
    MatchedResponsibility,
    RelationshipType,
)
from app.services.user_lookup import effective_role_names, find_user_or_404


def _query_error(message: str, field: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": message,
                "details": [{"field": f"query.{field}", "message": message, "type": "value_error"}],
            }
        }
    )


def _matches(requested: Optional[str], *candidates: Optional[str]) -> bool:
    """A requested department/faculty may be given by ID or by code (case-insensitive)."""
    if not requested:
        return True
    wanted = requested.strip().lower()
    return any(c is not None and c.strip().lower() == wanted for c in candidates)


class EligibilityService:
    def __init__(self, db: Session, directory: DirectoryClient):
        self.repository = UserRepository(db)
        self.directory = directory

    @staticmethod
    def validate_query(
        relationship: Optional[RelationshipType],
        department_id: Optional[str],
        faculty_id: Optional[str],
        service_unit_id: Optional[str],
    ) -> None:
        has_unit = any([department_id, faculty_id, service_unit_id])
        if has_unit and relationship is None:
            raise _query_error("'relationship' is required when an organizational unit is given.", "relationship")
        if relationship is not None and not has_unit:
            raise _query_error(
                "An organizational unit (department_id, faculty_id or service_unit_id) is required "
                "when 'relationship' is given.", "relationship")
        if relationship == RelationshipType.AFFILIATION and service_unit_id:
            raise _query_error("Affiliations link users to departments and faculties, not service units.",
                               "service_unit_id")

    def evaluate(
        self,
        user_id: str,
        required_role: Optional[str] = None,
        relationship: Optional[RelationshipType] = None,
        department_id: Optional[str] = None,
        faculty_id: Optional[str] = None,
        service_unit_id: Optional[str] = None,
    ) -> EligibilityData:
        self.validate_query(relationship, department_id, faculty_id, service_unit_id)
        user = find_user_or_404(self.repository, user_id)
        roles = effective_role_names(user)
        reasons: List[EligibilityReason] = []

        # Stage 1: identity checks (Identity DB)
        account_active = user.status == AccountStatus.ACTIVE
        if not account_active:
            reasons.append(EligibilityReason.ACCOUNT_INACTIVE)

        normalized_role = required_role.strip().upper() if required_role else None
        role_held = None
        if normalized_role:
            role_held = normalized_role in (r.upper() for r in roles)
            if not role_held:
                reasons.append(EligibilityReason.ROLE_NOT_HELD)

        checks = EligibilityChecks(
            account_active=account_active,
            required_role=normalized_role,
            role_held=role_held,
            relationship=relationship,
        )
        matched: List[MatchedResponsibility] = []
        affiliation_summary: Optional[AffiliationSummary] = None

        # Stage 2: organizational relationship (Directory Service), only when identity checks
        # pass, so an already-ineligible user never depends on Directory availability.
        if relationship is not None and not reasons:
            try:
                if relationship == RelationshipType.RESPONSIBILITY:
                    satisfied, matched = self._check_responsibility(
                        user.id, service_unit_id, department_id, faculty_id, reasons)
                else:
                    satisfied, affiliation_summary = self._check_affiliation(
                        user.id, department_id, faculty_id, reasons)
            except DirectoryServiceUnavailable:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "success": False,
                        "error": {
                            "code": "DEPENDENCY_UNAVAILABLE",
                            "message": "The Directory Service is currently unavailable, so eligibility "
                                       "could not be determined. Please retry later."
                        }
                    }
                )
            except DirectoryServiceError:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={
                        "success": False,
                        "error": {
                            "code": "DEPENDENCY_ERROR",
                            "message": "The Directory Service returned an unexpected response, so "
                                       "eligibility could not be determined."
                        }
                    }
                )
            checks.relationship_satisfied = satisfied

        return EligibilityData(
            user_id=user.id,
            university_id=user.university_id,
            account_status=user.status,
            roles=roles,
            eligible=not reasons,
            reasons=reasons,
            message=REASON_MESSAGES[reasons[0]] if reasons else "User is eligible.",
            checks=checks,
            matched_responsibilities=matched,
            affiliation=affiliation_summary,
        )

    def _check_responsibility(self, user_id, service_unit_id, department_id, faculty_id, reasons):
        result = self.directory.get_user_responsibilities(
            user_id, service_unit_id=service_unit_id, department_id=department_id, faculty_id=faculty_id
        )
        if result.outcome == ResponsibilityOutcome.NONE:
            reasons.append(EligibilityReason.NO_MATCHING_RESPONSIBILITY)
            return False, []
        if result.outcome == ResponsibilityOutcome.INACTIVE:
            reasons.append(EligibilityReason.RESPONSIBILITY_INACTIVE)
            return False, []
        matched = [
            MatchedResponsibility(**record.model_dump(exclude={"status"}))
            for record in result.responsibilities if record.status == "ACTIVE"
        ]
        return True, matched

    def _check_affiliation(self, user_id, department_id, faculty_id, reasons):
        affiliation = self.directory.get_user_affiliation(user_id)
        if affiliation is None:
            reasons.append(EligibilityReason.NO_AFFILIATION)
            return False, None

        summary = AffiliationSummary(
            department_id=affiliation.department_id,
            department_name=affiliation.department_name,
            faculty_id=affiliation.faculty_id,
            faculty_name=affiliation.faculty_name,
        )
        satisfied = (
            _matches(department_id, affiliation.department_id, affiliation.department_code)
            and _matches(faculty_id, affiliation.faculty_id, affiliation.faculty_code)
        )
        if not satisfied:
            reasons.append(EligibilityReason.AFFILIATION_MISMATCH)
        return satisfied, summary

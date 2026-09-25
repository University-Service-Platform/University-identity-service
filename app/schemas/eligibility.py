from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.user import AccountStatus


class RelationshipType(str, Enum):
    AFFILIATION = "AFFILIATION"        # user belongs to the department/faculty (e.g. a student's department)
    RESPONSIBILITY = "RESPONSIBILITY"  # user holds a responsibility for the unit (e.g. staff of a service unit)


class EligibilityReason(str, Enum):
    ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE"
    ROLE_NOT_HELD = "ROLE_NOT_HELD"
    NO_AFFILIATION = "NO_AFFILIATION"
    AFFILIATION_MISMATCH = "AFFILIATION_MISMATCH"
    NO_MATCHING_RESPONSIBILITY = "NO_MATCHING_RESPONSIBILITY"
    RESPONSIBILITY_INACTIVE = "RESPONSIBILITY_INACTIVE"


REASON_MESSAGES = {
    EligibilityReason.ACCOUNT_INACTIVE: "User account is inactive.",
    EligibilityReason.ROLE_NOT_HELD: "User does not hold the required role.",
    EligibilityReason.NO_AFFILIATION: "User has no organizational affiliation.",
    EligibilityReason.AFFILIATION_MISMATCH: "User is not affiliated with the requested department/faculty.",
    EligibilityReason.NO_MATCHING_RESPONSIBILITY: "User has no responsibility for the requested organizational unit.",
    EligibilityReason.RESPONSIBILITY_INACTIVE: "User's responsibility for the requested organizational unit is inactive.",
}


class EligibilityChecks(BaseModel):
    account_active: bool
    required_role: Optional[str] = None
    role_held: Optional[bool] = Field(None, description="null when no role was requested")
    relationship: Optional[RelationshipType] = None
    relationship_satisfied: Optional[bool] = Field(
        None, description="null when no relationship was requested or it was not evaluated"
    )


class MatchedResponsibility(BaseModel):
    responsibility_id: str
    role_title: str
    service_unit_id: Optional[str] = None
    service_unit_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    faculty_id: Optional[str] = None
    faculty_name: Optional[str] = None


class AffiliationSummary(BaseModel):
    department_id: str
    department_name: Optional[str] = None
    faculty_id: str
    faculty_name: Optional[str] = None


class EligibilityData(BaseModel):
    user_id: str = Field(..., examples=["usr-servicedesk-001"])
    university_id: str = Field(..., examples=["SDO001"])
    account_status: AccountStatus
    roles: List[str]
    eligible: bool = Field(..., description="True only when every requested check passes")
    reasons: List[EligibilityReason] = Field(default_factory=list, description="Why the user is not eligible")
    message: str = Field(..., examples=["User is eligible."])
    checks: EligibilityChecks
    matched_responsibilities: List[MatchedResponsibility] = Field(default_factory=list)
    affiliation: Optional[AffiliationSummary] = None


class EligibilityResponse(BaseModel):
    success: bool = True
    data: EligibilityData

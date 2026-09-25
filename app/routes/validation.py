from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.dependencies.auth import require_active_account
from app.integrations.directory_client import DirectoryClient, get_directory_client
from app.models.user import User
from app.services.eligibility_service import EligibilityService
from app.services.user_validation_service import UserValidationService
from app.schemas.eligibility import EligibilityResponse, RelationshipType
from app.schemas.validation import (
    ServiceUserValidationData,
    ServiceUserValidationResponse,
    UserValidationResponse,
)

# Sprint 1 route, kept unchanged (unauthenticated, includes email) as a deprecated alias.
router = APIRouter(tags=["Validation"])

# /api/v1 route: callers must forward a valid JWT, and contact details are not exposed.
v1_router = APIRouter(tags=["Validation"])

REQUIRE_ACTIVE_QUERY = Query(False, description="If true, returns 403 Forbidden for INACTIVE accounts")
REQUIRED_ROLE_QUERY = Query(None, description="Optional role to check if user is authorized for specific role/operation")


@router.get(
    "/validation/users/{user_id}",
    response_model=UserValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate User Identity and Role (USM-42 & USM-124)",
    description="Validate user existence, identifier format, account status, identity details, role relationships, and evaluate role authorization for external requesting services."
)
def validate_user_account(
    user_id: str,
    require_active: bool = REQUIRE_ACTIVE_QUERY,
    required_role: Optional[str] = REQUIRED_ROLE_QUERY,
    db: Session = Depends(get_db)
):
    service = UserValidationService(db)
    validation_data = service.validate_user_account(
        user_id=user_id,
        require_active=require_active,
        required_role=required_role
    )
    return UserValidationResponse(success=True, data=validation_data)


@v1_router.get(
    "/validation/users/{user_id}",
    response_model=ServiceUserValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate User Identity and Role",
    description="For other services: validate that a user exists, whether the account is active, which roles it "
                "holds and, optionally, whether it holds `required_role`. Requires a valid Bearer token "
                "(forward the requesting user's JWT). Unknown users return 404 USER_NOT_FOUND; with "
                "`require_active=true`, inactive users return 403 ACCOUNT_INACTIVE."
)
def validate_user_account_v1(
    user_id: str,
    require_active: bool = REQUIRE_ACTIVE_QUERY,
    required_role: Optional[str] = REQUIRED_ROLE_QUERY,
    db: Session = Depends(get_db),
    caller: User = Depends(require_active_account)
):
    validation_data = UserValidationService(db).validate_user_account(
        user_id=user_id,
        require_active=require_active,
        required_role=required_role
    )
    return ServiceUserValidationResponse(
        success=True,
        data=ServiceUserValidationData(**validation_data.model_dump(exclude={"email"}))
    )


@v1_router.get(
    "/validation/users/{user_id}/eligibility",
    response_model=EligibilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate Eligibility (Identity + Role + Organizational Relationship)",
    description="For other services: decide whether a user may perform an action that depends on system role "
                "AND department/service responsibility. Identity and role come from the Identity DB; "
                "affiliations and responsibilities come from the Directory Service API.\n\n"
                "Returns 200 with `eligible` true/false and machine-readable `reasons`. Unknown users return "
                "404 USER_NOT_FOUND. If the Directory Service is needed but unavailable the response is "
                "503 DEPENDENCY_UNAVAILABLE (never a guessed answer). Requires a valid Bearer token."
)
def validate_eligibility(
    request: Request,
    user_id: str,
    required_role: Optional[str] = Query(None, description="Role the user must hold, e.g. RESOURCE_MANAGER"),
    relationship: Optional[RelationshipType] = Query(
        None, description="AFFILIATION (member of the unit) or RESPONSIBILITY (responsible for the unit); "
                          "required when a unit is given"),
    department_id: Optional[str] = Query(None, description="Directory department ID (or code for AFFILIATION)"),
    faculty_id: Optional[str] = Query(None, description="Directory faculty ID (or code for AFFILIATION)"),
    service_unit_id: Optional[str] = Query(None, description="Directory service unit ID (RESPONSIBILITY only)"),
    db: Session = Depends(get_db),
    directory: DirectoryClient = Depends(get_directory_client),
    caller: User = Depends(require_active_account)
):
    service = EligibilityService(db, directory.with_authorization(request.headers.get("Authorization")))
    data = service.evaluate(
        user_id=user_id,
        required_role=required_role,
        relationship=relationship,
        department_id=department_id,
        faculty_id=faculty_id,
        service_unit_id=service_unit_id,
    )
    return EligibilityResponse(success=True, data=data)

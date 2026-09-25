from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.dependencies.auth import require_active_account
from app.models.user import User
from app.services.user_validation_service import UserValidationService
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

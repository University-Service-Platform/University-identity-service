from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.services.user_validation_service import UserValidationService
from app.schemas.validation import UserValidationResponse, APIResponse

router = APIRouter(tags=["Validation"])

@router.get(
    "/validation/users/{user_id}",
    response_model=UserValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate User Identity and Role (USM-42 & USM-124)",
    description="Validate user existence, identifier format, account status, identity details, role relationships, and evaluate role authorization for external requesting services."
)
def validate_user_account(
    user_id: str,
    require_active: bool = Query(False, description="If true, returns 403 Forbidden for INACTIVE accounts"),
    required_role: Optional[str] = Query(None, description="Optional role to check if user is authorized for specific role/operation"),
    db: Session = Depends(get_db)
):
    service = UserValidationService(db)
    validation_data = service.validate_user_account(
        user_id=user_id,
        require_active=require_active,
        required_role=required_role
    )
    return UserValidationResponse(success=True, data=validation_data)

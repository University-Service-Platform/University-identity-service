from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.user_validation_service import UserValidationService
from app.schemas.validation import UserValidationResponse, APIResponse

router = APIRouter(tags=["Validation"])

@router.get(
    "/validation/users/{user_id}",
    response_model=UserValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate User Account",
    description="Validate user existence, identifier format, account status, identity details, and role relationships. Reusable API for inter-service integration."
)
def validate_user_account(
    user_id: str,
    require_active: bool = Query(False, description="If true, returns 403 Forbidden for INACTIVE accounts"),
    db: Session = Depends(get_db)
):
    service = UserValidationService(db)
    validation_data = service.validate_user_account(user_id=user_id, require_active=require_active)
    return UserValidationResponse(success=True, data=validation_data)

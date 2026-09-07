from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.role_identification_service import RoleIdentificationService
from app.schemas.role import UserRoleIdentificationResponse
from app.dependencies.auth import require_active_account
from app.models.user import User

router = APIRouter(tags=["Role Identification"])

@router.get(
    "/users/{user_id}/role",
    response_model=UserRoleIdentificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Identify User Role",
    description="Retrieve current user role(s) from the single source of truth (Identity DB). Reflects immediate role assignments/updates."
)
def get_user_role(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_account)
):
    service = RoleIdentificationService(db)
    role_data = service.get_user_role(user_id=user_id)
    return UserRoleIdentificationResponse(success=True, data=role_data)

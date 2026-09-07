from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.profile_access_service import ProfileAccessService
from app.schemas.profile import UserProfileResponse
from app.dependencies.auth import require_active_account
from app.models.user import User

router = APIRouter(tags=["User Profiles"])

@router.get(
    "/users/{user_id}",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Protected User Profile",
    description="Retrieve user profile data. Protected access: users can view their own profile; authorized staff/admins can view any user profile."
)
def get_user_profile(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_account)
):
    service = ProfileAccessService(db)
    profile_data = service.get_user_profile(target_user_id=user_id, requester=current_user)
    return UserProfileResponse(success=True, data=profile_data)

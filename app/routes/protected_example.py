from fastapi import APIRouter, Depends, status
from app.dependencies.auth import require_active_account
from app.models.user import User

router = APIRouter(tags=["Protected Access"])

@router.get(
    "/protected/user-status",
    status_code=status.HTTP_200_OK,
    summary="Protected Account Status Demonstration",
    description="Protected endpoint requiring a valid authentication token AND an ACTIVE account status."
)
def get_protected_user_status(
    current_user: User = Depends(require_active_account)
):
    return {
        "success": True,
        "data": {
            "message": "Access granted. Account status is ACTIVE.",
            "user_id": current_user.id,
            "university_id": current_user.university_id,
            "status": current_user.status
        }
    }

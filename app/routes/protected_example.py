from fastapi import APIRouter, Depends, status
from app.dependencies.auth import require_active_account, RoleChecker
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

@router.get(
    "/protected/admin-only",
    status_code=status.HTTP_200_OK,
    summary="Admin-Only Protected Route",
    description="Protected endpoint requiring ADMIN role authorization."
)
def get_admin_only_resource(
    current_user: User = Depends(RoleChecker(["ADMIN"]))
):
    return {
        "success": True,
        "data": {
            "message": "Access granted. User possesses ADMIN role.",
            "user_id": current_user.id
        }
    }

@router.get(
    "/protected/staff-only",
    status_code=status.HTTP_200_OK,
    summary="Staff/Admin Protected Route",
    description="Protected endpoint requiring STAFF or ADMIN role authorization."
)
def get_staff_only_resource(
    current_user: User = Depends(RoleChecker(["STAFF", "ADMIN"]))
):
    return {
        "success": True,
        "data": {
            "message": "Access granted. User possesses STAFF or ADMIN role.",
            "user_id": current_user.id
        }
    }

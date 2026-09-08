from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.profile_access_service import ProfileAccessService
from app.services.user_management_service import UserManagementService
from app.schemas.profile import UserProfileResponse
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserStatusUpdate,
    UserSingleResponse,
    UserListResponse
)
from app.dependencies.auth import require_active_account, RoleChecker
from app.models.user import User

router = APIRouter(tags=["Users"])

@router.post(
    "/users",
    response_model=UserSingleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create User Account",
    description="Create a new student or staff user account. Accessible by authorized administrators."
)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["ADMIN"]))
):
    service = UserManagementService(db)
    user_data = service.create_user(user_in)
    return UserSingleResponse(success=True, data=user_data)

@router.get(
    "/users",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List User Accounts",
    description="Retrieve a list of user accounts. Accessible by authorized administrators and staff."
)
def list_users(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max items to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["ADMIN", "STAFF"]))
):
    service = UserManagementService(db)
    users_data = service.list_users(skip=skip, limit=limit)
    return UserListResponse(success=True, data=users_data)

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

@router.put(
    "/users/{user_id}",
    response_model=UserSingleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Account",
    description="Update permitted account fields (name, email, account_type). Accessible by authorized administrators."
)
def update_user(
    user_id: str,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["ADMIN"]))
):
    service = UserManagementService(db)
    updated_user = service.update_user(user_id=user_id, user_update=user_update)
    return UserSingleResponse(success=True, data=updated_user)

@router.patch(
    "/users/{user_id}/status",
    response_model=UserSingleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Account Status",
    description="Activate or deactivate a user account. Accessible by authorized administrators."
)
def update_user_status(
    user_id: str,
    status_in: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["ADMIN"]))
):
    service = UserManagementService(db)
    updated_user = service.update_user_status(user_id=user_id, new_status=status_in.status)
    return UserSingleResponse(success=True, data=updated_user)

@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete User Account",
    description="Permanently delete a user account and associated role records. Accessible by authorized administrators."
)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["ADMIN"]))
):
    service = UserManagementService(db)
    service.delete_user(user_id=user_id)
    return {
        "success": True,
        "data": {
            "message": f"User '{user_id}' was successfully deleted."
        }
    }

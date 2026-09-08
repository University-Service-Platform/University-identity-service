from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.role_identification_service import RoleIdentificationService
from app.services.role_assignment_service import RoleAssignmentService
from app.schemas.role import (
    UserRoleIdentificationResponse,
    UserRoleAssignRequest,
    UserRoleUpdateRequest,
    UserRoleAssignmentResponse
)
from app.dependencies.auth import require_active_account, RoleChecker
from app.models.user import User

router = APIRouter(tags=["Role Management & Identification"])

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

@router.post(
    "/users/{user_id}/roles",
    response_model=UserRoleAssignmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign Role to User",
    description="Assign an existing system role to a user account. Accessible by authorized administrators."
)
def assign_user_role(
    user_id: str,
    role_in: UserRoleAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["ADMIN"]))
):
    service = RoleAssignmentService(db)
    assignment_data = service.assign_role(user_id=user_id, role_name=role_in.role_name)
    return UserRoleAssignmentResponse(success=True, data=assignment_data)

@router.put(
    "/users/{user_id}/roles",
    response_model=UserRoleAssignmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User-Role Relationship (USM-94)",
    description="Update an existing user-role relationship for a user account. Accessible by authorized administrators. Updated authorization applies to subsequent requests."
)
def update_user_role(
    user_id: str,
    role_in: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["ADMIN"]))
):
    service = RoleAssignmentService(db)
    update_data = service.update_user_role(
        user_id=user_id,
        old_role_name=role_in.old_role_name,
        new_role_name=role_in.new_role_name
    )
    return UserRoleAssignmentResponse(success=True, data=update_data)

@router.delete(
    "/users/{user_id}/roles/{role_name}",
    response_model=UserRoleAssignmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke Role from User",
    description="Revoke an assigned system role from a user account. Accessible by authorized administrators."
)
def revoke_user_role(
    user_id: str,
    role_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["ADMIN"]))
):
    service = RoleAssignmentService(db)
    revocation_data = service.revoke_role(user_id=user_id, role_name=role_name)
    return UserRoleAssignmentResponse(success=True, data=revocation_data)

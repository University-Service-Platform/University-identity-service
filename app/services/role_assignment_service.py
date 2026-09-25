from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.role import UserRole
from app.repositories.user_repository import UserRepository
from app.repositories.role_repository import RoleRepository
from app.schemas.role import UserRoleAssignmentData
from app.services.user_lookup import find_user_or_404

class RoleAssignmentService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repository = UserRepository(db)
        self.role_repository = RoleRepository(db)

    def assign_role(self, user_id: str, role_name: str) -> UserRoleAssignmentData:
        # Steps 1-2: Validate identifier and find user
        user = find_user_or_404(self.user_repository, user_id)

        # Step 3: Find role by name (normalized)
        normalized_role_name = role_name.strip().upper()
        role = self.role_repository.get_role_by_name(normalized_role_name)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "ROLE_NOT_FOUND",
                        "message": f"Role '{normalized_role_name}' does not exist."
                    }
                }
            )

        # Step 4: Check if already assigned
        existing_link = self.role_repository.get_user_role_link(user_id=user.id, role_id=role.id)
        if existing_link:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "success": False,
                    "error": {
                        "code": "ROLE_ALREADY_ASSIGNED",
                        "message": f"Role '{normalized_role_name}' is already assigned to user '{user.university_id}'."
                    }
                }
            )

        # Step 5: Assign UserRole
        new_link = UserRole(user_id=user.id, role_id=role.id)
        self.role_repository.add_user_role(new_link)

        # Step 6: Fetch current active roles
        user_roles = [r.upper() for r in self.user_repository.get_user_roles(user.id)]
        primary_role = user_roles[0] if user_roles else user.account_type.value

        return UserRoleAssignmentData(
            user_id=user.id,
            university_id=user.university_id,
            name=user.name,
            roles=user_roles,
            primary_role=primary_role,
            message=f"Role '{normalized_role_name}' successfully assigned to user."
        )

    def revoke_role(self, user_id: str, role_name: str) -> UserRoleAssignmentData:
        # Steps 1-2: Validate identifier and find user
        user = find_user_or_404(self.user_repository, user_id)

        # Step 3: Find role by name
        normalized_role_name = role_name.strip().upper()
        role = self.role_repository.get_role_by_name(normalized_role_name)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "ROLE_NOT_FOUND",
                        "message": f"Role '{normalized_role_name}' does not exist."
                    }
                }
            )

        # Step 4: Find UserRole link
        existing_link = self.role_repository.get_user_role_link(user_id=user.id, role_id=role.id)
        if not existing_link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "ROLE_NOT_ASSIGNED",
                        "message": f"User '{user.university_id}' does not possess role '{normalized_role_name}'."
                    }
                }
            )

        # Step 5: Remove UserRole link
        self.role_repository.remove_user_role(existing_link)

        # Step 6: Fetch updated roles
        user_roles = [r.upper() for r in self.user_repository.get_user_roles(user.id)]
        primary_role = user_roles[0] if user_roles else user.account_type.value
        if not user_roles:
            user_roles = [user.account_type.value]

        return UserRoleAssignmentData(
            user_id=user.id,
            university_id=user.university_id,
            name=user.name,
            roles=user_roles,
            primary_role=primary_role,
            message=f"Role '{normalized_role_name}' successfully revoked from user."
        )

    def update_user_role(self, user_id: str, old_role_name: str, new_role_name: str) -> UserRoleAssignmentData:
        """
        USM-94 Update User-Role Relationships.
        Replaces an existing assigned role with a new target system role for a user.
        Rejects invalid role targets, missing existing assignments, and non-existent users.
        """
        # Steps 1-2: Validate identifier and find user
        user = find_user_or_404(self.user_repository, user_id)

        # Step 3: Validate old role exists and is assigned
        norm_old_role = old_role_name.strip().upper()
        old_role = self.role_repository.get_role_by_name(norm_old_role)
        if not old_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "ROLE_NOT_FOUND",
                        "message": f"Old role '{norm_old_role}' does not exist."
                    }
                }
            )

        existing_link = self.role_repository.get_user_role_link(user_id=user.id, role_id=old_role.id)
        if not existing_link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "ROLE_NOT_ASSIGNED",
                        "message": f"User '{user.university_id}' does not possess role '{norm_old_role}' to update."
                    }
                }
            )

        # Step 4: Validate new role exists
        norm_new_role = new_role_name.strip().upper()
        new_role = self.role_repository.get_role_by_name(norm_new_role)
        if not new_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "ROLE_NOT_FOUND",
                        "message": f"Target new role '{norm_new_role}' does not exist."
                    }
                }
            )

        # Step 5: Perform update on UserRole link
        existing_link.role_id = new_role.id
        self.db.commit()
        self.db.refresh(existing_link)

        # Step 6: Return updated role list
        user_roles = [r.upper() for r in self.user_repository.get_user_roles(user.id)]
        primary_role = user_roles[0] if user_roles else user.account_type.value

        return UserRoleAssignmentData(
            user_id=user.id,
            university_id=user.university_id,
            name=user.name,
            roles=user_roles,
            primary_role=primary_role,
            message=f"User role relationship updated from '{norm_old_role}' to '{norm_new_role}' successfully."
        )

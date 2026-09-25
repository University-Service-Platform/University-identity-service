import re
from typing import List

from fastapi import HTTPException, status

from app.models.user import User
from app.repositories.user_repository import UserRepository

IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,50}$")


def is_valid_identifier(identifier: str) -> bool:
    """Identifiers are alphanumeric with optional hyphens/underscores, between 3 and 50 chars."""
    if not identifier or not isinstance(identifier, str):
        return False
    return bool(IDENTIFIER_PATTERN.match(identifier.strip()))


def require_valid_identifier(identifier: str, label: str = "User identifier") -> None:
    if not is_valid_identifier(identifier):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_IDENTIFIER_FORMAT",
                    "message": f"{label} '{identifier}' has an invalid format."
                }
            }
        )


def find_user_or_404(repository: UserRepository, identifier: str, resource_label: str = "User") -> User:
    """
    Resolve a user by internal ID or university ID.
    Raises 400 for a malformed identifier and 404 when no user matches.
    """
    require_valid_identifier(identifier)

    user = repository.get_by_id(identifier)
    if not user:
        user = repository.get_by_university_id(identifier)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": f"{resource_label} with identifier '{identifier}' was not found."
                }
            }
        )
    return user


def effective_role_names(user: User) -> List[str]:
    """
    Roles assigned to the user in the Identity DB.
    Falls back to the account type (STUDENT/STAFF) when no explicit role has been assigned.
    """
    roles = [link.role.name for link in user.roles if link.role]
    if not roles and user.account_type:
        roles = [user.account_type.value]
    return roles

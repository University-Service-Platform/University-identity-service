"""Keep the platform administrable: at least one active ADMIN must always remain."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.role import Role, UserRole
from app.models.user import AccountStatus, User
from app.repositories.user_repository import UserRepository
from app.services.user_lookup import effective_role_names, find_user_or_404

ADMIN_ROLE = "ADMIN"


def _is_active_admin(user: User) -> bool:
    return user.status == AccountStatus.ACTIVE and ADMIN_ROLE in effective_role_names(user)


def count_active_admins(db: Session) -> int:
    return (db.query(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .filter(Role.name == ADMIN_ROLE, User.status == AccountStatus.ACTIVE)
            .distinct()
            .count())


def ensure_admin_remains(db: Session, user_id: str) -> None:
    """Refuse (409 LAST_ADMIN) to delete, deactivate or demote the only active administrator."""
    user = find_user_or_404(UserRepository(db), user_id)
    if _is_active_admin(user) and count_active_admins(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"success": False, "error": {
                "code": "LAST_ADMIN",
                "message": "This is the only active administrator. Make another user an ADMIN first."}}
        )


def ensure_not_self(current_user: User, user_id: str, action: str) -> None:
    """Refuse (400 CANNOT_CHANGE_OWN_ACCOUNT) to let administrators delete or deactivate themselves."""
    target = user_id.strip().lower()
    if target in (current_user.id.lower(), current_user.university_id.lower()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "error": {
                "code": "CANNOT_CHANGE_OWN_ACCOUNT",
                "message": f"You can't {action} your own account. Ask another administrator."}}
        )

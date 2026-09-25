from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_permission
from app.models.user import User
from app.schemas.audit import AuditLogListResponse
from app.services.audit_service import AuditService

router = APIRouter(tags=["Audit"])

@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Audit Log Entries",
    description="Administrative and security actions (user changes, status changes, role changes, password "
                "events, logins), newest first. Requires the 'audit:read' permission."
)
def list_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action, e.g. USER_STATUS_CHANGED"),
    actor_user_id: Optional[str] = Query(None, description="Filter by the user who performed the action"),
    target_id: Optional[str] = Query(None, description="Filter by the affected user ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit:read"))
):
    entries = AuditService(db).list_entries(
        action=action, actor_user_id=actor_user_id, target_id=target_id, skip=skip, limit=limit
    )
    return AuditLogListResponse(success=True, data=entries)

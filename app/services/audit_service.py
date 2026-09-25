import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogEntry

# Recorded actions
USER_CREATED = "USER_CREATED"
USER_UPDATED = "USER_UPDATED"
USER_DELETED = "USER_DELETED"
USER_STATUS_CHANGED = "USER_STATUS_CHANGED"
ROLE_ASSIGNED = "ROLE_ASSIGNED"
ROLE_UPDATED = "ROLE_UPDATED"
ROLE_REVOKED = "ROLE_REVOKED"
PASSWORD_SET = "PASSWORD_SET"
PASSWORD_CHANGED = "PASSWORD_CHANGED"
LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        actor_user_id: Optional[str],
        action: str,
        target_type: str,
        target_id: Optional[str],
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.db.add(AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=json.dumps(details, default=str, sort_keys=True) if details else None,
        ))
        self.db.commit()

    def list_entries(
        self,
        action: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        target_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLogEntry]:
        query = self.db.query(AuditLog)
        if action:
            query = query.filter(AuditLog.action == action.strip().upper())
        if actor_user_id:
            query = query.filter(AuditLog.actor_user_id == actor_user_id)
        if target_id:
            query = query.filter(AuditLog.target_id == target_id)
        rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(skip).limit(limit).all()
        return [
            AuditLogEntry(
                id=row.id,
                actor_user_id=row.actor_user_id,
                action=row.action,
                target_type=row.target_type,
                target_id=row.target_id,
                details=json.loads(row.details) if row.details else {},
                created_at=row.created_at,
            )
            for row in rows
        ]

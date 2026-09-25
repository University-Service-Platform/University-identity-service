from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    id: int
    actor_user_id: Optional[str] = Field(None, description="User who performed the action")
    action: str = Field(..., examples=["USER_STATUS_CHANGED"])
    target_type: str = Field(..., examples=["USER"])
    target_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict, examples=[{"status": "INACTIVE"}])
    created_at: datetime


class AuditLogListResponse(BaseModel):
    success: bool = True
    data: List[AuditLogEntry]

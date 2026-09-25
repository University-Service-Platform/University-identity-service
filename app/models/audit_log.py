from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.time import utc_now
from app.database import Base

class AuditLog(Base):
    """
    Append-only record of administrative and security-relevant actions.
    Actor and target IDs are plain strings (no foreign keys) so entries survive
    deletion of the users they refer to.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    actor_user_id = Column(String(36), index=True, nullable=True)
    action = Column(String(50), index=True, nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(50), index=True, nullable=True)
    details = Column(Text, nullable=True)  # JSON object
    created_at = Column(DateTime, default=utc_now, index=True, nullable=False)

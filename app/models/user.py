from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from app.core.time import utc_now
from app.database import Base

class AccountType(str, enum.Enum):
    STUDENT = "STUDENT"
    STAFF = "STAFF"

class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, index=True)
    university_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    account_type = Column(SQLEnum(AccountType), nullable=False)
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False)
    # bcrypt hash; NULL means no password has been set and the account cannot log in yet
    password_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")

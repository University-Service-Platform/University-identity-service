from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.models.user import AccountType, AccountStatus

class UserBase(BaseModel):
    university_id: str
    name: str
    email: EmailStr
    account_type: AccountType

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: str
    status: AccountStatus
    created_at: datetime
    roles: List[str] = []

    model_config = ConfigDict(from_attributes=True)

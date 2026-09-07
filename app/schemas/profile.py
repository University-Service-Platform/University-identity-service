from pydantic import BaseModel, EmailStr, ConfigDict
from typing import List, Optional
from datetime import datetime
from app.models.user import AccountType, AccountStatus

class UserProfileData(BaseModel):
    user_id: str
    university_id: str
    name: str
    email: EmailStr
    account_type: AccountType
    status: AccountStatus
    roles: List[str] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserProfileResponse(BaseModel):
    success: bool = True
    data: UserProfileData

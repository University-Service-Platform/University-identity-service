from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from app.models.user import AccountType, AccountStatus

class UserBase(BaseModel):
    university_id: str = Field(..., min_length=3, max_length=50, description="University ID, e.g. STU001 or STF001")
    name: str = Field(..., min_length=1, max_length=100, description="Full Name")
    email: EmailStr = Field(..., description="University Email Address")
    account_type: AccountType = Field(..., description="STUDENT or STAFF")

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Updated Full Name")
    email: Optional[EmailStr] = Field(None, description="Updated University Email")
    account_type: Optional[AccountType] = Field(None, description="Updated Account Type")

class UserStatusUpdate(BaseModel):
    status: AccountStatus = Field(..., description="Target account status: ACTIVE or INACTIVE")

class UserResponse(UserBase):
    id: str
    status: AccountStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    roles: List[str] = []

    model_config = ConfigDict(from_attributes=True)

class UserSingleResponse(BaseModel):
    success: bool = True
    data: UserResponse

class UserListResponse(BaseModel):
    success: bool = True
    data: List[UserResponse]

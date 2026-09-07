from pydantic import BaseModel, Field
from typing import List, Optional, Any
from app.models.user import AccountType, AccountStatus

class ErrorDetail(BaseModel):
    code: str
    message: str

class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[ErrorDetail] = None

class UserValidationData(BaseModel):
    user_id: str
    university_id: str
    name: str
    email: str
    account_type: AccountType
    status: AccountStatus
    is_valid: bool
    roles: List[str] = []

class UserValidationResponse(BaseModel):
    success: bool = True
    data: UserValidationData

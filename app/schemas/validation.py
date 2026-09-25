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
    is_authorized: bool = True
    required_role_checked: Optional[str] = None

class UserValidationResponse(BaseModel):
    success: bool = True
    data: UserValidationData

class ServiceUserValidationData(BaseModel):
    """
    /api/v1 user validation result for other services.
    Omits contact details (email): consumers only need identity, status and roles.
    """
    user_id: str = Field(..., examples=["usr-student-001"])
    university_id: str = Field(..., examples=["STU001"])
    name: str = Field(..., examples=["Demo Student"])
    account_type: AccountType
    status: AccountStatus
    is_valid: bool = Field(..., description="True when the account is ACTIVE")
    roles: List[str] = Field(default_factory=list, examples=[["STUDENT"]])
    is_authorized: bool = Field(True, description="False when required_role was given and the user does not hold it")
    required_role_checked: Optional[str] = None

class ServiceUserValidationResponse(BaseModel):
    success: bool = True
    data: ServiceUserValidationData

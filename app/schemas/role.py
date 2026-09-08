from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from app.models.user import AccountType

class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class UserRoleData(BaseModel):
    user_id: str
    university_id: str
    name: str
    account_type: AccountType
    roles: List[str]
    primary_role: str

class UserRoleIdentificationResponse(BaseModel):
    success: bool = True
    data: UserRoleData

class UserRoleAssignRequest(BaseModel):
    role_name: str = Field(..., min_length=2, max_length=50, description="Role name to assign (e.g. ADMIN, STAFF, DEAN)")

class UserRoleUpdateRequest(BaseModel):
    old_role_name: str = Field(..., min_length=2, max_length=50, description="Existing assigned role name to replace")
    new_role_name: str = Field(..., min_length=2, max_length=50, description="New role name to assign")

class UserRoleAssignmentData(BaseModel):
    user_id: str
    university_id: str
    name: str
    roles: List[str]
    primary_role: str
    message: str

class UserRoleAssignmentResponse(BaseModel):
    success: bool = True
    data: UserRoleAssignmentData

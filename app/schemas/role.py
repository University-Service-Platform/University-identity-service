from pydantic import BaseModel, ConfigDict
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

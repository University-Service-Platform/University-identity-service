from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import List, Optional
from datetime import datetime
from app.models.user import AccountType, AccountStatus
from app.schemas.directory import AffiliationStatus, AffiliationSummary

class UserProfileData(BaseModel):
    user_id: str
    university_id: str
    name: str
    email: EmailStr
    account_type: AccountType
    status: AccountStatus
    roles: List[str] = []
    created_at: datetime
    # Department/faculty from the Directory Service (not stored by the Identity Service)
    affiliation: Optional[AffiliationSummary] = None
    affiliation_status: AffiliationStatus = Field(
        AffiliationStatus.NOT_CONFIGURED,
        description="Whether the affiliation could be retrieved; the profile is returned even when it could not"
    )

    model_config = ConfigDict(from_attributes=True)

class UserProfileResponse(BaseModel):
    success: bool = True
    data: UserProfileData

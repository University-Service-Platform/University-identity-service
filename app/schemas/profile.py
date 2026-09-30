from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import List, Optional
from datetime import datetime
from app.models.user import AccountType, AccountStatus
from app.schemas.directory import AffiliationStatus, AffiliationSummary
from app.schemas.names import NameParts

class UserProfileData(NameParts):
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

class OwnProfileUpdate(BaseModel):
    """
    Self-service profile edit. The shared frontend sends camelCase (firstName, lastName, email, phone),
    so both spellings are accepted. Only the name can be changed here: the email is the login identifier
    and stays admin-managed, and phone numbers are not stored by the Identity Service.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Full name (or send first_name + last_name)")
    first_name: Optional[str] = Field(None, alias="firstName", max_length=100)
    last_name: Optional[str] = Field(None, alias="lastName", max_length=100)
    email: Optional[EmailStr] = Field(None, description="Must equal the current email; changes need an administrator")
    phone: Optional[str] = Field(None, description="Accepted for frontend compatibility; not stored")

    model_config = ConfigDict(populate_by_name=True)

    def full_name(self) -> Optional[str]:
        if self.name is not None:
            return self.name.strip()
        parts = [p.strip() for p in (self.first_name, self.last_name) if p and p.strip()]
        return " ".join(parts) or None

class UserProfileResponse(BaseModel):
    success: bool = True
    data: UserProfileData

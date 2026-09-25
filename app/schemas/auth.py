from typing import Annotated, List

from pydantic import AfterValidator, BaseModel, Field

from app.core.security import BCRYPT_MAX_PASSWORD_BYTES
from app.models.user import AccountStatus, AccountType


def _check_password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must not exceed {BCRYPT_MAX_PASSWORD_BYTES} bytes.")
    return value


Password = Annotated[
    str,
    Field(min_length=8, max_length=BCRYPT_MAX_PASSWORD_BYTES, description="8 to 72 characters"),
    AfterValidator(_check_password_bytes),
]


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100, description="University ID or email address",
                          examples=["STU001"])
    password: str = Field(..., min_length=1, max_length=BCRYPT_MAX_PASSWORD_BYTES)


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token lifetime in seconds")
    user_id: str
    university_id: str
    roles: List[str]


class TokenResponse(BaseModel):
    success: bool = True
    data: TokenData


class CurrentIdentityData(BaseModel):
    user_id: str
    university_id: str
    name: str
    email: str
    account_type: AccountType
    status: AccountStatus
    roles: List[str]
    primary_role: str
    permissions: List[str] = Field(..., description="Identity Service permissions granted by the user's roles")


class CurrentIdentityResponse(BaseModel):
    success: bool = True
    data: CurrentIdentityData


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=BCRYPT_MAX_PASSWORD_BYTES)
    new_password: Password


class PasswordSetRequest(BaseModel):
    new_password: Password


class MessageData(BaseModel):
    message: str


class MessageResponse(BaseModel):
    success: bool = True
    data: MessageData

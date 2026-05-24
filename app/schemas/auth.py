from pydantic import BaseModel, ConfigDict, EmailStr, model_validator


class UserLogin(BaseModel):
    """Schema for user login - requires either email or username"""
    email: EmailStr | None = None
    username: str | None = None
    password: str

    @model_validator(mode='after')
    def validate_email_or_username(self): # email takes precedence over username
        if not self.email and not self.username:
            raise ValueError('Either email or username must be provided')
        return self

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

from pydantic import BaseModel, EmailStr
from datetime import datetime


class UserCreate(BaseModel):
    """Schema for creating a new user"""
    email: EmailStr
    username: str
    password: str

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """Schema for user response (without sensitive data)"""
    id: int
    email: str
    username: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


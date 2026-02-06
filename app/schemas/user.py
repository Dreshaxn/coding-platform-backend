from pydantic import BaseModel, EmailStr
from datetime import datetime
from app.schemas.user_stats import UserStatsPublicResponse, UserStatsSummary


# ============================================================================
# Input Schemas
# ============================================================================

class UserCreate(BaseModel):
    """Schema for creating a new user"""
    email: EmailStr
    username: str
    password: str

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating user profile"""
    bio: str | None = None
    school: str | None = None
    avatar_url: str | None = None
    languages: str | None = None  # Preferred programming languages

    class Config:
        from_attributes = True


# ============================================================================
# Response Schemas
# ============================================================================

class UserResponse(BaseModel):
    """Full user response with stats (for profile pages)"""
    id: int
    email: str
    username: str
    bio: str | None = None
    school: str | None = None
    avatar_url: str | None = None
    languages: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Stats from UserStats relationship
    stats: UserStatsPublicResponse | None = None

    class Config:
        from_attributes = True


class UserPublicResponse(BaseModel):
    """Public user profile (no email)"""
    id: int
    username: str
    bio: str | None = None
    school: str | None = None
    avatar_url: str | None = None
    languages: str | None = None
    created_at: datetime
    
    # Public stats
    stats: UserStatsPublicResponse | None = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Minimal user for lists/leaderboards"""
    id: int
    username: str
    avatar_url: str | None = None
    stats: UserStatsSummary | None = None

    class Config:
        from_attributes = True


class UserMeResponse(BaseModel):
    """Current authenticated user response"""
    id: int
    email: str
    username: str
    bio: str | None = None
    school: str | None = None
    avatar_url: str | None = None
    languages: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    stats: UserStatsPublicResponse | None = None

    class Config:
        from_attributes = True

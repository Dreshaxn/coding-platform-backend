from pydantic import BaseModel


# ============================================================================
# Base Schemas
# ============================================================================

class LanguageBase(BaseModel):
    """Base fields for programming languages"""
    slug: str  # e.g., "python3", "javascript"
    name: str  # e.g., "Python 3", "JavaScript (Node.js)"
    version: str  # e.g., "3.11", "18.x"


# ============================================================================
# Input Schemas
# ============================================================================

class LanguageCreate(LanguageBase):
    """Schema for creating a new language"""
    boilerplate_code: str | None = None
    file_extension: str
    compile_command: str | None = None
    run_command: str
    is_active: bool = True


class LanguageUpdate(BaseModel):
    """Schema for updating a language (all fields optional)"""
    name: str | None = None
    version: str | None = None
    boilerplate_code: str | None = None
    file_extension: str | None = None
    compile_command: str | None = None
    run_command: str | None = None
    is_active: bool | None = None


# ============================================================================
# Response Schemas
# ============================================================================

class LanguageResponse(LanguageBase):
    """Full language response (for API)"""
    id: int
    boilerplate_code: str | None = None
    file_extension: str
    is_active: bool

    class Config:
        from_attributes = True


class LanguageListResponse(BaseModel):
    """Minimal language response for dropdowns/lists"""
    id: int
    slug: str
    name: str
    version: str

    class Config:
        from_attributes = True



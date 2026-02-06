from datetime import datetime
from pydantic import BaseModel


# ============================================================================
# Base Schemas
# ============================================================================

class TestCaseBase(BaseModel):
    """Base fields for test cases"""
    input: str  # JSON-encoded input parameters
    expected_output: str  # JSON-encoded expected result
    is_hidden: bool = False
    order: int = 0


# ============================================================================
# Input Schemas
# ============================================================================

class TestCaseCreate(TestCaseBase):
    """Schema for creating a test case (problem_id provided separately)"""
    pass


class TestCaseUpdate(BaseModel):
    """Schema for updating a test case (all fields optional)"""
    input: str | None = None
    expected_output: str | None = None
    is_hidden: bool | None = None
    order: int | None = None


# ============================================================================
# Response Schemas
# ============================================================================

class TestCaseResponse(TestCaseBase):
    """Full test case response (for admins/problem authors)"""
    id: int
    problem_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestCasePublicResponse(BaseModel):
    """Public test case response (hides expected output for non-hidden cases)"""
    id: int
    input: str
    expected_output: str | None = None  # Only shown for visible test cases
    order: int

    class Config:
        from_attributes = True




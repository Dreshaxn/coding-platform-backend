from datetime import datetime
from pydantic import BaseModel, ConfigDict


# ============================================================================
# Base Schemas
# ============================================================================

class ProblemBase(BaseModel):
    title: str
    description: str
    difficulty_id: int
    category_id: int
    function_name: str


class CategoryBase(BaseModel):
    name: str
    description: str | None = None


class DifficultyBase(BaseModel):
    name: str
    value: int


# ============================================================================
# Input Schemas (for creating new records)
# ============================================================================

class ProblemCreate(ProblemBase):
    pass


class CategoryCreate(CategoryBase):
    pass


class DifficultyCreate(DifficultyBase):
    pass


# ============================================================================
# Response Schemas (for API responses)
# ============================================================================

class DifficultyResponse(DifficultyBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class CategoryResponse(CategoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ProblemResponse(ProblemBase):
    id: int
    difficulty: DifficultyResponse
    category: CategoryResponse
    created_at: datetime
    updated_at: datetime
    function_name: str

    model_config = ConfigDict(from_attributes=True)


class UserSolvedProblemResponse(BaseModel):
    id: int
    user_id: int
    problem_id: int
    solved_at: datetime

    model_config = ConfigDict(from_attributes=True)

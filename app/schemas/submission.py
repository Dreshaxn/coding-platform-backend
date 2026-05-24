from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict
from app.schemas.language import LanguageListResponse


class SubmissionBase(BaseModel):
    problem_id: int
    language_id: int
    code: str


class SubmissionCreate(SubmissionBase):
    pass


class SubmissionResponse(BaseModel):
    id: int
    user_id: int
    problem_id: int
    language_id: int
    code: str
    status: str
    passed: bool = False
    passed_count: int = 0
    total_count: int = 0
    results: list[dict[str, Any]] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmissionWithLanguageResponse(SubmissionResponse):
    language: LanguageListResponse

    model_config = ConfigDict(from_attributes=True)


class SubmissionListResponse(BaseModel):
    id: int
    problem_id: int
    language_id: int
    status: str
    passed_count: int = 0
    total_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmissionResultResponse(BaseModel):
    id: int
    status: str
    passed: bool = False
    passed_count: int = 0
    total_count: int = 0
    results: list[dict[str, Any]] | None = None

    model_config = ConfigDict(from_attributes=True)

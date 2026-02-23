from datetime import datetime
from pydantic import BaseModel


class ProblemTemplateBase(BaseModel):
    boilerplate_code: str


class ProblemTemplateCreate(ProblemTemplateBase):
    problem_id: int
    language_id: int


class ProblemTemplateResponse(ProblemTemplateBase):
    id: int
    problem_id: int
    language_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

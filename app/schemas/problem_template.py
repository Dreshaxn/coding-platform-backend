from datetime import datetime
from pydantic import BaseModel, ConfigDict


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

    model_config = ConfigDict(from_attributes=True)

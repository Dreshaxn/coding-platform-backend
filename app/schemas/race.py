from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.race import RaceParticipantStatus, RaceStatus


class RaceBase(BaseModel):
    name: str
    time_limit: int


class RaceCreate(RaceBase):
    problem_id: int | None = None
    difficulty_id: int | None = None
    category_id: int | None = None
    language_id: int | None = None


class RaceUpdate(BaseModel):
    name: str | None = None
    status: RaceStatus | None = None
    time_limit: int | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None


class RaceResponse(RaceBase):
    id: int
    creator_id: int
    status: RaceStatus
    problem_id: int
    winner_id: int | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RaceParticipantCreate(BaseModel):
    language_id: int | None = None


class RaceParticipantUpdate(BaseModel):
    is_ready: bool | None = None
    language_id: int | None = None
    progress: int | None = None
    final_status: RaceParticipantStatus | None = None


class RaceParticipantResponse(BaseModel):
    id: int
    race_id: int
    is_ready: bool
    user_id: int
    language_id: int
    joined_at: datetime
    progress: int
    final_status: RaceParticipantStatus

    model_config = ConfigDict(from_attributes=True)


class RaceSubmissionCreate(BaseModel):
    code: str
    language_id: int


class RaceSubmissionResponse(BaseModel):
    id: int
    submission_id: int
    race_id: int
    participant_id: int
    problem_id: int
    verdict: str
    code: str
    started_at: datetime
    language_id: int
    total_test: int

    model_config = ConfigDict(from_attributes=True)


class RaceProgressResponse(BaseModel):
    race: RaceResponse
    participants: list[RaceParticipantResponse]
    submissions: list[RaceSubmissionResponse]

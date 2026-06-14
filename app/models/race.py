import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.utils.datetime import utcnow_naive


class RaceStatus(str, enum.Enum):
    WAITING = "waiting"
    READY = "ready"
    RUNNING = "running"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class RaceParticipantStatus(str, enum.Enum):
    ACTIVE = "active"
    FINISHED = "finished"
    LEFT = "left"
    DISQUALIFIED = "disqualified"


class Race(Base):
    __tablename__ = "races"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(RaceStatus), default=RaceStatus.WAITING, nullable=False, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True)
    time_limit = Column(Integer, nullable=False)
    winner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False)

    creator = relationship("User", foreign_keys=[creator_id], back_populates="created_races")
    winner = relationship("User", foreign_keys=[winner_id])
    problem = relationship("Problem", back_populates="races")
    participants = relationship(
        "RaceParticipant",
        back_populates="race",
        cascade="all, delete-orphan",
    )
    submissions = relationship(
        "RaceSubmission",
        back_populates="race",
        cascade="all, delete-orphan",
    )


class RaceParticipant(Base):
    __tablename__ = "race_participants"
    __table_args__ = (
        UniqueConstraint("race_id", "user_id", name="uq_race_participant_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    race_id = Column(Integer, ForeignKey("races.id", ondelete="CASCADE"), nullable=False, index=True)
    is_ready = Column(Boolean, nullable=False, default=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    language_id = Column(Integer, ForeignKey("languages.id"), nullable=False, index=True)
    joined_at = Column(DateTime, default=utcnow_naive, nullable=False)
    progress = Column(Integer, default=0, nullable=False)
    final_status = Column(
        Enum(RaceParticipantStatus),
        default=RaceParticipantStatus.ACTIVE,
        nullable=False,
    )

    race = relationship("Race", back_populates="participants")
    user = relationship("User", back_populates="race_participations")
    language = relationship("Language", back_populates="race_participants")
    submissions = relationship(
        "RaceSubmission",
        back_populates="participant",
        cascade="all, delete-orphan",
    )


class RaceSubmission(Base):
    __tablename__ = "race_submissions"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, unique=True)
    race_id = Column(Integer, ForeignKey("races.id", ondelete="CASCADE"), nullable=False, index=True)
    participant_id = Column(Integer, ForeignKey("race_participants.id", ondelete="CASCADE"), nullable=False, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True)
    verdict = Column(String(50), nullable=False)
    code = Column(Text, nullable=False)
    started_at = Column(DateTime, default=utcnow_naive, nullable=False)
    language_id = Column(Integer, ForeignKey("languages.id"), nullable=False, index=True)
    total_test = Column(Integer, default=0, nullable=False)

    submission = relationship("Submission", back_populates="race_submission")
    race = relationship("Race", back_populates="submissions")
    participant = relationship("RaceParticipant", back_populates="submissions")
    problem = relationship("Problem", back_populates="race_submissions")
    language = relationship("Language", back_populates="race_submissions")

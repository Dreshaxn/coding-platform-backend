from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON, Enum
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime
import enum


class SubmissionStatus(str, enum.Enum):
    """Status of a code submission."""
    PENDING = "pending"
    RUNNING = "running"
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    COMPILATION_ERROR = "compilation_error"


class Submission(Base):
    __tablename__ = "submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    language_id = Column(Integer, ForeignKey("languages.id"), nullable=False)
    code = Column(Text, nullable=False)  # The submitted code
    status = Column(Enum(SubmissionStatus), default=SubmissionStatus.PENDING, nullable=False)
    
    # Results
    passed = Column(Boolean, nullable=False, default=False)
    passed_count = Column(Integer, nullable=False, default=0)
    total_count = Column(Integer, nullable=False, default=0)
    results = Column(JSON, nullable=True)  # Detailed test case results
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    problem = relationship("Problem", back_populates="submissions")
    user = relationship("User", back_populates="submissions")
    language = relationship("Language", back_populates="submissions")

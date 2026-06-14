from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.utils.datetime import utcnow_naive


class Problem(Base):
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=False)
    difficulty_id = Column(Integer, ForeignKey("difficulties.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)

    # Required method name on the Solution class (e.g. "twoSum").
    # The judge always wraps user code with a driver that calls Solution().method_name(*args).
    function_name = Column(String(100), nullable=False)

    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False)

    # Relationships
    category = relationship("Category", back_populates="problems")
    difficulty = relationship("Difficulty", back_populates="problems")
    test_cases = relationship("TestCase", back_populates="problem", cascade="all, delete-orphan")
    templates = relationship("ProblemTemplate", back_populates="problem", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="problem")
    races = relationship("Race", back_populates="problem", cascade="all, delete-orphan")
    race_submissions = relationship("RaceSubmission", back_populates="problem")
    solved_users = relationship(
        "UserSolvedProblem",
        back_populates="problem",
        cascade="all, delete-orphan"
    )

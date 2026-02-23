from sqlalchemy import Column, Integer, Text, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime


class ProblemTemplate(Base):
    """
    Per-problem, per-language boilerplate code (LeetCode-style).

    Stores the Solution class skeleton that users see in the editor.
    Example for Python Two Sum:
        class Solution:
            def twoSum(self, nums: List[int], target: int) -> List[int]:
                pass
    """
    __tablename__ = "problem_templates"
    __table_args__ = (
        UniqueConstraint("problem_id", "language_id", name="uq_problem_language"),
    )

    id = Column(Integer, primary_key=True, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True)
    language_id = Column(Integer, ForeignKey("languages.id", ondelete="CASCADE"), nullable=False, index=True)
    boilerplate_code = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    problem = relationship("Problem", back_populates="templates")
    language = relationship("Language", back_populates="templates")

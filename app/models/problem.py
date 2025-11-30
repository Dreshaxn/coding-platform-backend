from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime


class Problem(Base):
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=False)
    difficulty_id = Column(Integer, ForeignKey("difficulties.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    category = relationship("Category", back_populates="problems")
    difficulty = relationship("Difficulty", back_populates="problems")
    solved_users = relationship(
        "UserSolvedProblem",
        back_populates="problem",
        cascade="all, delete-orphan"
    )


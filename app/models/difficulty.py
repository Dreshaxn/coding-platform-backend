from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base


class Difficulty(Base):
    __tablename__ = "difficulties"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)  # "easy", "medium", "hard"
    value = Column(Integer, nullable=False)  # easy=1, medium=2, hard=3

    # Relationships
    problems = relationship("Problem", back_populates="difficulty")


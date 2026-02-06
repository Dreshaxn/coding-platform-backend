from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    refresh_token_hash = Column(String, nullable=True)

    # --- Profile fields ---
    bio = Column(String, nullable=True)
    school = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    languages = Column(String, nullable=True)  # Preferred languages, could be JSON later

    # Relationships
    solved_problems = relationship(
        "UserSolvedProblem",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # One-to-one with UserStats (keeps User table lightweight)
    stats = relationship(
        "UserStats",
        back_populates="user",
        uselist=False,  # One-to-one relationship
        cascade="all, delete-orphan"
    )
    
    # User's submissions
    submissions = relationship(
        "Submission",
        back_populates="user",
        cascade="all, delete-orphan"
    )

from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime


class UserStats(Base):
    """
    Separate table for user statistics to keep the users table lightweight.
    Enables complex metrics (rank, percentile) without bloating the core user entity.
    One-to-one relationship with User.
    """
    __tablename__ = "user_stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # Core stats
    xp = Column(Integer, default=0, nullable=False)
    streak = Column(Integer, default=0, nullable=False)
    longest_streak = Column(Integer, default=0, nullable=False)
    
    # Problem solving stats
    problems_solved = Column(Integer, default=0, nullable=False)
    easy_solved = Column(Integer, default=0, nullable=False)
    medium_solved = Column(Integer, default=0, nullable=False)
    hard_solved = Column(Integer, default=0, nullable=False)
    
    # Submission stats
    total_submissions = Column(Integer, default=0, nullable=False)
    accepted_submissions = Column(Integer, default=0, nullable=False)
    
    # Ranking metrics (updated periodically via background job)
    global_rank = Column(Integer, nullable=True)
    global_percentile = Column(Float, nullable=True)  # e.g., 95.5 means top 4.5%
    
    # Contest stats
    contests_participated = Column(Integer, default=0, nullable=False)
    best_contest_rank = Column(Integer, nullable=True)
    
    # Timestamps
    last_submission_at = Column(DateTime, nullable=True)
    last_streak_update = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    user = relationship("User", back_populates="stats")


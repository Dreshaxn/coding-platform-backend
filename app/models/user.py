from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.db.base import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users" # Table name
    id = Column(Integer, primary_key=True, index=True) # Primary key
    email = Column(String, unique=True, index=True, nullable=False) # Email
    username = Column(String, unique=True, index=True, nullable=False) # Username
    is_active = Column(Boolean, default=True) # Is active
    hashed_password = Column(String, nullable=False) # Hashed password  
    created_at = Column(DateTime, default=datetime.now) # Created at
    updated_at = Column(DateTime, default=datetime.now) # Updated at
    refresh_token_hash = Column(String, nullable=True)

     # --- Profile fields ---
    bio = Column(String, nullable=True)
    school = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    languages = Column(String, nullable=True)  # could be JSON later

    # --- Stats fields ---
    xp = Column(Integer, default=0)
    streak = Column(Integer, default=0)
    problems_solved = Column(Integer, default=0)
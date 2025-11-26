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
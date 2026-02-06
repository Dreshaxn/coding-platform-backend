from sqlalchemy import Column, Integer, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime


class TestCase(Base):
    """
    Stores test cases for problems.
    Each problem can have multiple test cases (some visible, some hidden).
    """
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Input/output as JSON text - flexible for various data types
    input = Column(Text, nullable=False)  # JSON-encoded input parameters
    expected_output = Column(Text, nullable=False)  # JSON-encoded expected result
    
    # Hidden tests are used for final validation but not shown to users
    is_hidden = Column(Boolean, default=False, nullable=False)
    
    # Optional: ordering for consistent test execution
    order = Column(Integer, default=0, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    problem = relationship("Problem", back_populates="test_cases")


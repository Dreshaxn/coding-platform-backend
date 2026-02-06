from sqlalchemy import Column, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base


class Language(Base):
    """
    Lookup table for supported programming languages.
    Provides versioning, boilerplate code, and execution configuration.
    """
    __tablename__ = "languages"

    id = Column(Integer, primary_key=True, index=True)
    
    # Identifiers
    slug = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "python3", "javascript"
    name = Column(String(100), nullable=False)  # e.g., "Python 3", "JavaScript (Node.js)"
    version = Column(String(50), nullable=False)  # e.g., "3.11", "18.x"
    
    # Code templates
    boilerplate_code = Column(Text, nullable=True)  # Default starter code template
    
    # Execution configuration
    file_extension = Column(String(10), nullable=False)  # e.g., ".py", ".js"
    compile_command = Column(String(255), nullable=True)  # For compiled languages
    run_command = Column(String(255), nullable=False)  # Command to execute code
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)  # Enable/disable language support

    # Relationships
    submissions = relationship("Submission", back_populates="language")


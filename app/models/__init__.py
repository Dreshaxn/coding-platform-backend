# Import all models here so Alembic can detect them
# This file is imported by alembic/env.py to ensure all models are registered
from app.models.user import User  # noqa: F401

__all__ = ["User"]

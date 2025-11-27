# app/db/base.py

from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Note: Models are imported in alembic/env.py for Alembic to detect them
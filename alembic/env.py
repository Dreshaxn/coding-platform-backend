from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

import os

# --- Import Base ---
from app.db.base import Base

# --- Import ALL MODELS ---
# Import from models/__init__.py to ensure all models are registered with Base.metadata
from app.models import (  # noqa: F401
    User,
    Category,
    Difficulty,
    Problem,
    UserSolvedProblem,
)

# --- Import settings (loads .env) ---
from app.core.config import settings


# ------------------------
# Alembic Config
# ------------------------
config = context.config

# Replace sqlalchemy.url using your .env DATABASE_URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# ------------------------
# Logging
# ------------------------
if config.config_file_name is not None and os.path.exists(config.config_file_name):
    try:
        fileConfig(config.config_file_name)
    except KeyError as e:
        # Handle the KeyError, e.g., by printing a warning or using a default logging config
        # For now, we'll just print a warning.
        print(f"Warning: Could not configure logging from alembic.ini: {e}. Proceeding without file-based logging configuration.")

# Tell Alembic what metadata to use for autogenerate
target_metadata = Base.metadata


# ------------------------
# OFFLINE MIGRATIONS
# ------------------------
def run_migrations_offline() -> None:
    """Run migrations without a DB connection."""
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ------------------------
# ONLINE MIGRATIONS
# ------------------------
def run_migrations_online() -> None:
    """Run migrations with a DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# ------------------------
# Run the correct mode
# ------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
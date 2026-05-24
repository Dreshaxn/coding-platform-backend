"""require function_name for driver-only execution

Revision ID: f12a3bc4d5e6
Revises: ca9d48032795
Create Date: 2026-04-18 00:00:00.000000

"""
from __future__ import annotations

import keyword
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f12a3bc4d5e6"
down_revision: Union[str, Sequence[str], None] = "ca9d48032795"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _to_identifier(title: str | None) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", title or "")
    if not parts:
        name = "solve"
    else:
        name = parts[0].lower() + "".join(p.capitalize() for p in parts[1:])

    if name and name[0].isdigit():
        name = f"p{name}"
    if keyword.iskeyword(name):
        name = f"{name}Fn"
    return name or "solve"


def upgrade() -> None:
    bind = op.get_bind()

    problems = sa.table(
        "problems",
        sa.column("id", sa.Integer),
        sa.column("title", sa.String(length=255)),
        sa.column("function_name", sa.String(length=100)),
    )

    rows = bind.execute(
        sa.select(problems.c.id, problems.c.title, problems.c.function_name).order_by(
            problems.c.id.asc()
        )
    ).fetchall()

    used: set[str] = set()
    for row in rows:
        if row.function_name and row.function_name.strip():
            used.add(row.function_name.strip())

    for row in rows:
        current = (row.function_name or "").strip()
        if current:
            continue

        base = _to_identifier(row.title)
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}{suffix}"
            suffix += 1

        bind.execute(
            problems.update().where(problems.c.id == row.id).values(function_name=candidate)
        )
        used.add(candidate)

    op.alter_column(
        "problems",
        "function_name",
        existing_type=sa.String(length=100),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "problems",
        "function_name",
        existing_type=sa.String(length=100),
        nullable=True,
    )

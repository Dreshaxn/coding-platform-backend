"""add race tables

Revision ID: 7b2a1d9e4c3f
Revises: f12a3bc4d5e6
Create Date: 2026-05-25 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b2a1d9e4c3f"
down_revision: Union[str, Sequence[str], None] = "f12a3bc4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


race_status = sa.Enum(
    "WAITING",
    "READY",
    "RUNNING",
    "FINISHED",
    "CANCELLED",
    name="racestatus",
)
race_participant_status = sa.Enum(
    "ACTIVE",
    "FINISHED",
    "LEFT",
    "DISQUALIFIED",
    name="raceparticipantstatus",
)


def upgrade() -> None:
    op.create_table(
        "races",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("status", race_status, nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=False),
        sa.Column("time_limit", sa.Integer(), nullable=False),
        sa.Column("winner_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["winner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_races_creator_id"), "races", ["creator_id"], unique=False)
    op.create_index(op.f("ix_races_id"), "races", ["id"], unique=False)
    op.create_index(op.f("ix_races_problem_id"), "races", ["problem_id"], unique=False)
    op.create_index(op.f("ix_races_status"), "races", ["status"], unique=False)
    op.create_index(op.f("ix_races_winner_id"), "races", ["winner_id"], unique=False)

    op.create_table(
        "race_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("is_ready", sa.Boolean(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("language_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("final_status", race_participant_status, nullable=False),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"]),
        sa.ForeignKeyConstraint(["race_id"], ["races.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("race_id", "user_id", name="uq_race_participant_user"),
    )
    op.create_index(
        op.f("ix_race_participants_id"),
        "race_participants",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_race_participants_language_id"),
        "race_participants",
        ["language_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_race_participants_race_id"),
        "race_participants",
        ["race_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_race_participants_user_id"),
        "race_participants",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "race_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=50), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("language_id", sa.Integer(), nullable=False),
        sa.Column("total_test", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"]),
        sa.ForeignKeyConstraint(["participant_id"], ["race_participants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["race_id"], ["races.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id"),
    )
    op.create_index(op.f("ix_race_submissions_id"), "race_submissions", ["id"], unique=False)
    op.create_index(
        op.f("ix_race_submissions_language_id"),
        "race_submissions",
        ["language_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_race_submissions_participant_id"),
        "race_submissions",
        ["participant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_race_submissions_problem_id"),
        "race_submissions",
        ["problem_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_race_submissions_race_id"),
        "race_submissions",
        ["race_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_race_submissions_race_id"), table_name="race_submissions")
    op.drop_index(op.f("ix_race_submissions_problem_id"), table_name="race_submissions")
    op.drop_index(op.f("ix_race_submissions_participant_id"), table_name="race_submissions")
    op.drop_index(op.f("ix_race_submissions_language_id"), table_name="race_submissions")
    op.drop_index(op.f("ix_race_submissions_id"), table_name="race_submissions")
    op.drop_table("race_submissions")

    op.drop_index(op.f("ix_race_participants_user_id"), table_name="race_participants")
    op.drop_index(op.f("ix_race_participants_race_id"), table_name="race_participants")
    op.drop_index(op.f("ix_race_participants_language_id"), table_name="race_participants")
    op.drop_index(op.f("ix_race_participants_id"), table_name="race_participants")
    op.drop_table("race_participants")

    op.drop_index(op.f("ix_races_winner_id"), table_name="races")
    op.drop_index(op.f("ix_races_status"), table_name="races")
    op.drop_index(op.f("ix_races_problem_id"), table_name="races")
    op.drop_index(op.f("ix_races_id"), table_name="races")
    op.drop_index(op.f("ix_races_creator_id"), table_name="races")
    op.drop_table("races")

    race_participant_status.drop(op.get_bind(), checkfirst=True)
    race_status.drop(op.get_bind(), checkfirst=True)

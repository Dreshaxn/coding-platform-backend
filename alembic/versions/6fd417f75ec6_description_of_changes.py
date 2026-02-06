"""description of changes

Revision ID: 6fd417f75ec6
Revises: 5a2e560e064d
Create Date: 2026-01-29 16:54:52.231254

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6fd417f75ec6'
down_revision: Union[str, Sequence[str], None] = '5a2e560e064d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type first
    submissionstatus = postgresql.ENUM(
        'PENDING', 'RUNNING', 'ACCEPTED', 'WRONG_ANSWER', 
        'TIME_LIMIT_EXCEEDED', 'MEMORY_LIMIT_EXCEEDED', 
        'RUNTIME_ERROR', 'COMPILATION_ERROR',
        name='submissionstatus'
    )
    submissionstatus.create(op.get_bind(), checkfirst=True)
    
    op.add_column('submissions', sa.Column('passed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('submissions', sa.Column('passed_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('submissions', sa.Column('total_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('submissions', sa.Column('results', sa.JSON(), nullable=True))
    op.add_column('submissions', sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
    
    # Convert status column to enum
    op.execute("ALTER TABLE submissions ALTER COLUMN status TYPE submissionstatus USING status::submissionstatus")
    op.drop_index(op.f('ix_submissions_language_id'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_problem_id'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_status'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_submitted_at'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_user_id'), table_name='submissions')
    op.drop_constraint(op.f('submissions_user_id_fkey'), 'submissions', type_='foreignkey')
    op.drop_constraint(op.f('submissions_problem_id_fkey'), 'submissions', type_='foreignkey')
    op.create_foreign_key(None, 'submissions', 'users', ['user_id'], ['id'])
    op.create_foreign_key(None, 'submissions', 'problems', ['problem_id'], ['id'])
    op.drop_column('submissions', 'error_message')
    op.drop_column('submissions', 'test_cases_total')
    op.drop_column('submissions', 'submitted_at')
    op.drop_column('submissions', 'memory_kb')
    op.drop_column('submissions', 'executed_at')
    op.drop_column('submissions', 'runtime_ms')
    op.drop_column('submissions', 'test_cases_passed')
    # ### end Alembic commands ###


def downgrade() -> None:
    op.add_column('submissions', sa.Column('test_cases_passed', sa.INTEGER(), autoincrement=False, nullable=False, server_default='0'))
    op.add_column('submissions', sa.Column('runtime_ms', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
    op.add_column('submissions', sa.Column('executed_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True))
    op.add_column('submissions', sa.Column('memory_kb', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
    op.add_column('submissions', sa.Column('submitted_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False, server_default=sa.func.now()))
    op.add_column('submissions', sa.Column('test_cases_total', sa.INTEGER(), autoincrement=False, nullable=False, server_default='0'))
    op.add_column('submissions', sa.Column('error_message', sa.TEXT(), autoincrement=False, nullable=True))
    
    # Convert status back to varchar
    op.execute("ALTER TABLE submissions ALTER COLUMN status TYPE VARCHAR(50) USING status::text")
    
    op.drop_column('submissions', 'created_at')
    op.drop_column('submissions', 'results')
    op.drop_column('submissions', 'total_count')
    op.drop_column('submissions', 'passed_count')
    op.drop_column('submissions', 'passed')
    
    # Drop enum type
    op.execute("DROP TYPE IF EXISTS submissionstatus")

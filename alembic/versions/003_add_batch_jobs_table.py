"""Add batch jobs table

Revision ID: 003_add_batch_jobs
Revises: 002_add_api_key_table
Create Date: 2025-07-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_add_batch_jobs'
down_revision: Union[str, None] = '002_add_api_key_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create batch_jobs table
    op.create_table('batch_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, default='pending'),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('total_jobs', sa.Integer(), nullable=False, default=0),
        sa.Column('completed_jobs', sa.Integer(), nullable=False, default=0),
        sa.Column('failed_jobs', sa.Integer(), nullable=False, default=0),
        sa.Column('processing_jobs', sa.Integer(), nullable=False, default=0),
        sa.Column('max_concurrent_jobs', sa.Integer(), nullable=False, default=5),
        sa.Column('priority', sa.Integer(), nullable=False, default=0),
        sa.Column('input_settings', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=3),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add batch_job_id column to jobs table
    op.add_column('jobs', sa.Column('batch_job_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key('fk_jobs_batch_job_id', 'jobs', 'batch_jobs', ['batch_job_id'], ['id'], ondelete='CASCADE')
    
    # Add indexes for performance
    op.create_index('ix_batch_jobs_status', 'batch_jobs', ['status'])
    op.create_index('ix_batch_jobs_user_id', 'batch_jobs', ['user_id'])
    op.create_index('ix_batch_jobs_created_at', 'batch_jobs', ['created_at'])
    op.create_index('ix_batch_jobs_priority', 'batch_jobs', ['priority'])
    op.create_index('ix_jobs_batch_job_id', 'jobs', ['batch_job_id'])


def downgrade() -> None:
    # Remove indexes
    op.drop_index('ix_jobs_batch_job_id', table_name='jobs')
    op.drop_index('ix_batch_jobs_priority', table_name='batch_jobs')
    op.drop_index('ix_batch_jobs_created_at', table_name='batch_jobs')
    op.drop_index('ix_batch_jobs_user_id', table_name='batch_jobs')
    op.drop_index('ix_batch_jobs_status', table_name='batch_jobs')
    
    # Remove foreign key constraint
    op.drop_constraint('fk_jobs_batch_job_id', 'jobs', type_='foreignkey')
    
    # Remove batch_job_id column from jobs table
    op.drop_column('jobs', 'batch_job_id')
    
    # Drop batch_jobs table
    op.drop_table('batch_jobs')
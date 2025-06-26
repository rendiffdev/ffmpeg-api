"""Initial schema creation

Revision ID: 001
Revises: 
Create Date: 2025-01-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite
from api.models.job import GUID

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create jobs table
    op.create_table('jobs',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('priority', sa.String(), nullable=False),
        sa.Column('input_path', sa.String(), nullable=False),
        sa.Column('output_path', sa.String(), nullable=False),
        sa.Column('input_metadata', sa.JSON(), nullable=True),
        sa.Column('output_metadata', sa.JSON(), nullable=True),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('operations', sa.JSON(), nullable=True),
        sa.Column('progress', sa.Float(), nullable=True),
        sa.Column('stage', sa.String(), nullable=True),
        sa.Column('fps', sa.Float(), nullable=True),
        sa.Column('eta_seconds', sa.Integer(), nullable=True),
        sa.Column('vmaf_score', sa.Float(), nullable=True),
        sa.Column('psnr_score', sa.Float(), nullable=True),
        sa.Column('ssim_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('worker_id', sa.String(), nullable=True),
        sa.Column('processing_time', sa.Float(), nullable=True),
        sa.Column('api_key', sa.String(), nullable=True),
        sa.Column('webhook_url', sa.String(), nullable=True),
        sa.Column('webhook_events', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_job_status_created', 'jobs', ['status', 'created_at'], unique=False)
    op.create_index('idx_job_api_key_created', 'jobs', ['api_key', 'created_at'], unique=False)
    op.create_index(op.f('ix_jobs_api_key'), 'jobs', ['api_key'], unique=False)
    op.create_index(op.f('ix_jobs_status'), 'jobs', ['status'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_jobs_status'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_api_key'), table_name='jobs')
    op.drop_index('idx_job_api_key_created', table_name='jobs')
    op.drop_index('idx_job_status_created', table_name='jobs')
    
    # Drop table
    op.drop_table('jobs')
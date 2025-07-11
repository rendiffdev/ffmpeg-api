"""Add API key table

Revision ID: 002
Revises: 001
Create Date: 2025-07-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from api.models.job import GUID

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create api_keys table
    op.create_table('api_keys',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('prefix', sa.String(length=8), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('owner_id', sa.String(length=100), nullable=True),
        sa.Column('owner_name', sa.String(length=100), nullable=True),
        sa.Column('owner_email', sa.String(length=200), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('max_concurrent_jobs', sa.Integer(), nullable=False),
        sa.Column('monthly_quota_minutes', sa.Integer(), nullable=False),
        sa.Column('total_jobs_created', sa.Integer(), nullable=False),
        sa.Column('total_minutes_processed', sa.Integer(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('revoked_by', sa.String(length=100), nullable=True),
        sa.Column('revocation_reason', sa.Text(), nullable=True),
        sa.Column('metadata', sa.String(length=1000), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
    
    # Create indexes
    op.create_index('idx_api_key_hash', 'api_keys', ['key_hash'], unique=False)
    op.create_index('idx_api_key_prefix', 'api_keys', ['prefix'], unique=False)
    op.create_index('idx_api_key_status_created', 'api_keys', ['status', 'created_at'], unique=False)
    op.create_index('idx_api_key_owner', 'api_keys', ['owner_id'], unique=False)
    op.create_index(op.f('ix_api_keys_key_hash'), 'api_keys', ['key_hash'], unique=True)
    op.create_index(op.f('ix_api_keys_prefix'), 'api_keys', ['prefix'], unique=False)
    op.create_index(op.f('ix_api_keys_status'), 'api_keys', ['status'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_api_keys_status'), table_name='api_keys')
    op.drop_index(op.f('ix_api_keys_prefix'), table_name='api_keys')
    op.drop_index(op.f('ix_api_keys_key_hash'), table_name='api_keys')
    op.drop_index('idx_api_key_owner', table_name='api_keys')
    op.drop_index('idx_api_key_status_created', table_name='api_keys')
    op.drop_index('idx_api_key_prefix', table_name='api_keys')
    op.drop_index('idx_api_key_hash', table_name='api_keys')
    
    # Drop table
    op.drop_table('api_keys')
"""Initial migration: doc_asset and audit_event tables

Revision ID: 001
Revises: 
Create Date: 2026-01-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create doc_asset table
    op.create_table(
        'doc_asset',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=512), nullable=False),
        sa.Column('storage_uri', sa.String(length=1024), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('indexed_status', sa.Enum('PENDING', 'INDEXING', 'READY', 'FAILED', name='indexedstatus'), nullable=False, server_default='PENDING'),
        sa.Column('datastore_ref', sa.String(length=512), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_doc_asset_id'), 'doc_asset', ['id'], unique=False)
    op.create_index(op.f('ix_doc_asset_filename'), 'doc_asset', ['filename'], unique=False)
    op.create_index(op.f('ix_doc_asset_indexed_status'), 'doc_asset', ['indexed_status'], unique=False)
    op.create_index(op.f('ix_doc_asset_deleted_at'), 'doc_asset', ['deleted_at'], unique=False)

    # Create audit_event table
    op.create_table(
        'audit_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('module', sa.Enum('MODULE_A', 'MODULE_B', 'MODULE_C', 'ADMIN', 'SYSTEM', name='auditmodule'), nullable=False),
        sa.Column('user_id', sa.String(length=128), nullable=True),
        sa.Column('session_id', sa.String(length=128), nullable=True),
        sa.Column('request_id', sa.String(length=128), nullable=False),
        sa.Column('prompt_hash', sa.String(length=64), nullable=True),
        sa.Column('sources_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('tool_calls_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('decision_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.Enum('SUCCESS', 'FAILURE', 'PENDING', name='auditstatus'), nullable=False, server_default='PENDING'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_event_id'), 'audit_event', ['id'], unique=False)
    op.create_index(op.f('ix_audit_event_ts'), 'audit_event', ['ts'], unique=False)
    op.create_index(op.f('ix_audit_event_module'), 'audit_event', ['module'], unique=False)
    op.create_index(op.f('ix_audit_event_user_id'), 'audit_event', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_event_session_id'), 'audit_event', ['session_id'], unique=False)
    op.create_index(op.f('ix_audit_event_request_id'), 'audit_event', ['request_id'], unique=False)
    op.create_index(op.f('ix_audit_event_prompt_hash'), 'audit_event', ['prompt_hash'], unique=False)
    op.create_index(op.f('ix_audit_event_status'), 'audit_event', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_event_status'), table_name='audit_event')
    op.drop_index(op.f('ix_audit_event_prompt_hash'), table_name='audit_event')
    op.drop_index(op.f('ix_audit_event_request_id'), table_name='audit_event')
    op.drop_index(op.f('ix_audit_event_session_id'), table_name='audit_event')
    op.drop_index(op.f('ix_audit_event_user_id'), table_name='audit_event')
    op.drop_index(op.f('ix_audit_event_module'), table_name='audit_event')
    op.drop_index(op.f('ix_audit_event_ts'), table_name='audit_event')
    op.drop_index(op.f('ix_audit_event_id'), table_name='audit_event')
    op.drop_table('audit_event')
    
    op.drop_index(op.f('ix_doc_asset_deleted_at'), table_name='doc_asset')
    op.drop_index(op.f('ix_doc_asset_indexed_status'), table_name='doc_asset')
    op.drop_index(op.f('ix_doc_asset_filename'), table_name='doc_asset')
    op.drop_index(op.f('ix_doc_asset_id'), table_name='doc_asset')
    op.drop_table('doc_asset')

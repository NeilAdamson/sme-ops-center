"""Add document domain lifecycle fields

Revision ID: 002
Revises: 001
Create Date: 2026-06-16

"""
from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


NEW_INDEXED_STATUS_VALUES = [
    "STAGED",
    "CLASSIFIED",
    "MOVING",
    "ARCHIVED",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in NEW_INDEXED_STATUS_VALUES:
            op.execute(f"ALTER TYPE indexedstatus ADD VALUE IF NOT EXISTS '{value}'")

    op.add_column("doc_asset", sa.Column("staging_uri", sa.String(length=1024), nullable=True))
    op.add_column("doc_asset", sa.Column("domain", sa.String(length=64), nullable=True))
    op.add_column("doc_asset", sa.Column("index_job_id", sa.String(length=128), nullable=True))
    op.add_column("doc_asset", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column(
        "doc_asset",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(op.f("ix_doc_asset_domain"), "doc_asset", ["domain"], unique=False)
    op.create_index(op.f("ix_doc_asset_index_job_id"), "doc_asset", ["index_job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_doc_asset_index_job_id"), table_name="doc_asset")
    op.drop_index(op.f("ix_doc_asset_domain"), table_name="doc_asset")
    op.drop_column("doc_asset", "updated_at")
    op.drop_column("doc_asset", "last_error")
    op.drop_column("doc_asset", "index_job_id")
    op.drop_column("doc_asset", "domain")
    op.drop_column("doc_asset", "staging_uri")

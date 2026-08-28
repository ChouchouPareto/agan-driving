"""add advisory knowledge documents

Revision ID: a62c8e17d904
Revises: 7c41ad89e205
"""
from alembic import op
import sqlalchemy as sa

revision = "a62c8e17d904"
down_revision = "7c41ad89e205"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "advisory_knowledge_documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("external_id", sa.String(), nullable=False, unique=True),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("source_org", sa.String(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("document_no", sa.String(), nullable=True),
        sa.Column("region", sa.String(), nullable=False),
        sa.Column("license_types", sa.JSON(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("published_at", sa.String(), nullable=True),
        sa.Column("effective_at", sa.String(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
    )
    for name in ("external_id", "topic", "region", "status"):
        op.create_index(f"ix_advisory_knowledge_documents_{name}", "advisory_knowledge_documents", [name])


def downgrade():
    op.drop_table("advisory_knowledge_documents")

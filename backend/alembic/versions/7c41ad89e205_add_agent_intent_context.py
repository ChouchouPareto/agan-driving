"""add agent intent context

Revision ID: 7c41ad89e205
Revises: 6f0e1a32b9c4
"""
from alembic import op
import sqlalchemy as sa

revision = "7c41ad89e205"
down_revision = "6f0e1a32b9c4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("questions", sa.Column("resolved_text", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("intent", sa.String(), nullable=False, server_default="QUESTION_ANSWER"))
    op.add_column("questions", sa.Column("prompt_version", sa.String(), nullable=False, server_default="pe-v1.0"))


def downgrade():
    op.drop_column("questions", "prompt_version")
    op.drop_column("questions", "intent")
    op.drop_column("questions", "resolved_text")

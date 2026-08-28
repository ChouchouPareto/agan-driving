"""add agent conversation turns

Revision ID: b73d9012f5aa
Revises: a62c8e17d904
"""
from alembic import op
import sqlalchemy as sa

revision = "b73d9012f5aa"
down_revision = "a62c8e17d904"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_turns",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("conversation_id", sa.String(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("student_id", sa.String(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("user_text", sa.Text(), nullable=False),
        sa.Column("assistant_text", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(), nullable=False),
        sa.Column("skill_id", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("token_usage", sa.Integer(), nullable=False),
        sa.Column("is_fallback", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name in ("conversation_id", "student_id", "intent"):
        op.create_index(f"ix_agent_turns_{name}", "agent_turns", [name])


def downgrade():
    op.drop_table("agent_turns")

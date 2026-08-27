"""add student practice progress

Revision ID: 6f0e1a32b9c4
Revises: 5e9d0f21a8b3
"""
from alembic import op
import sqlalchemy as sa

revision = "6f0e1a32b9c4"
down_revision = "5e9d0f21a8b3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("student_question_progress", sa.Column("id", sa.String(), primary_key=True), sa.Column("student_id", sa.String(), sa.ForeignKey("students.id"), nullable=False), sa.Column("standard_question_id", sa.String(), sa.ForeignKey("standard_questions.id"), nullable=False), sa.Column("knowledge_version_id", sa.String(), sa.ForeignKey("knowledge_versions.id"), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("correct_attempts", sa.Integer(), nullable=False), sa.Column("wrong_attempts", sa.Integer(), nullable=False), sa.Column("last_answer", sa.String(), nullable=True), sa.Column("last_correct", sa.Boolean(), nullable=True), sa.Column("is_favorite", sa.Boolean(), nullable=False), sa.Column("last_answered_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("student_id", "standard_question_id"))
    for name in ("student_id", "standard_question_id", "knowledge_version_id"): op.create_index(f"ix_student_question_progress_{name}", "student_question_progress", [name])


def downgrade():
    op.drop_table("student_question_progress")

"""add ocr pipeline

Revision ID: 8a27b2c0d1e2
Revises: c89181af4122
Create Date: 2026-08-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8a27b2c0d1e2"
down_revision: Union[str, None] = "c89181af4122"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "uploaded_assets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("student_id", sa.String(), nullable=False),
        sa.Column("school_id", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("original_name", sa.String(), nullable=False),
        sa.Column("safe_name", sa.String(), nullable=False),
        sa.Column("declared_mime", sa.String(), nullable=False),
        sa.Column("detected_mime", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(op.f("ix_uploaded_assets_student_id"), "uploaded_assets", ["student_id"])
    op.create_index(op.f("ix_uploaded_assets_school_id"), "uploaded_assets", ["school_id"])
    op.create_index(op.f("ix_uploaded_assets_sha256"), "uploaded_assets", ["sha256"])
    op.create_table(
        "ocr_tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("asset_id", sa.String(), nullable=False),
        sa.Column("student_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("question_type", sa.String(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message_safe", sa.String(), nullable=True),
        sa.Column("linked_question_id", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["uploaded_assets.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["linked_question_id"], ["questions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_ocr_tasks_asset_id"), "ocr_tasks", ["asset_id"])
    op.create_index(op.f("ix_ocr_tasks_student_id"), "ocr_tasks", ["student_id"])
    op.create_index(op.f("ix_ocr_tasks_status"), "ocr_tasks", ["status"])
    op.create_table(
        "ocr_fields",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("field_type", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("original_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("needs_confirmation", sa.Boolean(), nullable=False),
        sa.Column("corrected_value", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["ocr_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "field_type", "sequence"),
    )
    op.create_index(op.f("ix_ocr_fields_task_id"), "ocr_fields", ["task_id"])
    op.create_table(
        "ocr_audit_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("field_id", sa.String(), nullable=True),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("before_value", sa.Text(), nullable=True),
        sa.Column("after_value", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["field_id"], ["ocr_fields.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["ocr_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ocr_audit_logs_task_id"), "ocr_audit_logs", ["task_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ocr_audit_logs_task_id"), table_name="ocr_audit_logs")
    op.drop_table("ocr_audit_logs")
    op.drop_index(op.f("ix_ocr_fields_task_id"), table_name="ocr_fields")
    op.drop_table("ocr_fields")
    op.drop_index(op.f("ix_ocr_tasks_status"), table_name="ocr_tasks")
    op.drop_index(op.f("ix_ocr_tasks_student_id"), table_name="ocr_tasks")
    op.drop_index(op.f("ix_ocr_tasks_asset_id"), table_name="ocr_tasks")
    op.drop_table("ocr_tasks")
    op.drop_index(op.f("ix_uploaded_assets_sha256"), table_name="uploaded_assets")
    op.drop_index(op.f("ix_uploaded_assets_school_id"), table_name="uploaded_assets")
    op.drop_index(op.f("ix_uploaded_assets_student_id"), table_name="uploaded_assets")
    op.drop_table("uploaded_assets")

"""add rag evaluation gate

Revision ID: 5e9d0f21a8b3
Revises: 41d7a8b0c4f2
"""
from alembic import op
import sqlalchemy as sa

revision = "5e9d0f21a8b3"
down_revision = "41d7a8b0c4f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("evaluation_datasets", sa.Column("id", sa.String(), primary_key=True), sa.Column("school_id", sa.String(), nullable=False), sa.Column("name", sa.String(), nullable=False), sa.Column("version_label", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_evaluation_datasets_school_id", "evaluation_datasets", ["school_id"])
    op.create_table("evaluation_cases", sa.Column("id", sa.String(), primary_key=True), sa.Column("dataset_id", sa.String(), sa.ForeignKey("evaluation_datasets.id"), nullable=False), sa.Column("input_text", sa.Text(), nullable=False), sa.Column("expected_external_id", sa.String(), nullable=False), sa.Column("expected_answer", sa.String(), nullable=False), sa.Column("region", sa.String(), nullable=False), sa.Column("license_type", sa.String(), nullable=False), sa.Column("severity", sa.String(), nullable=False))
    op.create_index("ix_evaluation_cases_dataset_id", "evaluation_cases", ["dataset_id"])
    op.create_table("evaluation_runs", sa.Column("id", sa.String(), primary_key=True), sa.Column("dataset_id", sa.String(), sa.ForeignKey("evaluation_datasets.id"), nullable=False), sa.Column("knowledge_version_id", sa.String(), sa.ForeignKey("knowledge_versions.id"), nullable=False), sa.Column("status", sa.String(), nullable=False), sa.Column("embedding_model", sa.String(), nullable=False), sa.Column("rerank_model", sa.String(), nullable=False), sa.Column("total_cases", sa.Integer(), nullable=False), sa.Column("passed_cases", sa.Integer(), nullable=False), sa.Column("p0_errors", sa.Integer(), nullable=False), sa.Column("top1_rate", sa.Float(), nullable=False), sa.Column("answer_accuracy", sa.Float(), nullable=False), sa.Column("error_message_safe", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    for name in ("dataset_id", "knowledge_version_id", "status"): op.create_index(f"ix_evaluation_runs_{name}", "evaluation_runs", [name])
    op.create_table("evaluation_case_results", sa.Column("id", sa.String(), primary_key=True), sa.Column("run_id", sa.String(), sa.ForeignKey("evaluation_runs.id"), nullable=False), sa.Column("case_id", sa.String(), sa.ForeignKey("evaluation_cases.id"), nullable=False), sa.Column("matched_question_id", sa.String(), sa.ForeignKey("standard_questions.id"), nullable=True), sa.Column("actual_answer", sa.String(), nullable=True), sa.Column("passed", sa.Boolean(), nullable=False), sa.Column("error_code", sa.String(), nullable=True), sa.Column("match_type", sa.String(), nullable=False))
    op.create_index("ix_evaluation_case_results_run_id", "evaluation_case_results", ["run_id"]); op.create_index("ix_evaluation_case_results_case_id", "evaluation_case_results", ["case_id"])
    op.create_table("knowledge_activation_events", sa.Column("id", sa.String(), primary_key=True), sa.Column("school_id", sa.String(), nullable=False), sa.Column("actor_id", sa.String(), nullable=False), sa.Column("event_type", sa.String(), nullable=False), sa.Column("from_version_id", sa.String(), sa.ForeignKey("knowledge_versions.id"), nullable=True), sa.Column("to_version_id", sa.String(), sa.ForeignKey("knowledge_versions.id"), nullable=False), sa.Column("request_id", sa.String(), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_knowledge_activation_events_school_id", "knowledge_activation_events", ["school_id"]); op.create_index("ix_knowledge_activation_events_to_version_id", "knowledge_activation_events", ["to_version_id"]); op.create_index("ix_knowledge_activation_events_request_id", "knowledge_activation_events", ["request_id"])


def downgrade():
    for table in ("knowledge_activation_events", "evaluation_case_results", "evaluation_runs", "evaluation_cases", "evaluation_datasets"): op.drop_table(table)

"""add rag knowledge tables

Revision ID: 41d7a8b0c4f2
Revises: 27c2a310f321
"""
from alembic import op
import sqlalchemy as sa

revision = "41d7a8b0c4f2"
down_revision = "27c2a310f321"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("knowledge_sources", sa.Column("id", sa.String(), primary_key=True), sa.Column("school_id", sa.String(), nullable=False), sa.Column("name", sa.String(), nullable=False), sa.Column("supplier", sa.String(), nullable=False), sa.Column("license_scope", sa.String(), nullable=False), sa.Column("source_hash", sa.String(), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_knowledge_sources_school_id", "knowledge_sources", ["school_id"])
    op.create_table("knowledge_versions", sa.Column("id", sa.String(), primary_key=True), sa.Column("source_id", sa.String(), sa.ForeignKey("knowledge_sources.id"), nullable=False), sa.Column("school_id", sa.String(), nullable=False), sa.Column("version_label", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=False), sa.Column("region", sa.String(), nullable=False), sa.Column("license_type", sa.String(), nullable=False), sa.Column("schema_version", sa.String(), nullable=False), sa.Column("normalizer_version", sa.String(), nullable=False), sa.Column("embedding_model", sa.String(), nullable=False), sa.Column("embedding_dimensions", sa.Integer(), nullable=False), sa.Column("collection_name", sa.String(), nullable=True), sa.Column("item_count", sa.Integer(), nullable=False), sa.Column("error_count", sa.Integer(), nullable=False), sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_knowledge_versions_source_id", "knowledge_versions", ["source_id"]); op.create_index("ix_knowledge_versions_school_id", "knowledge_versions", ["school_id"]); op.create_index("ix_knowledge_versions_status", "knowledge_versions", ["status"])
    op.create_table("standard_questions", sa.Column("id", sa.String(), primary_key=True), sa.Column("knowledge_version_id", sa.String(), sa.ForeignKey("knowledge_versions.id"), nullable=False), sa.Column("school_id", sa.String(), nullable=False), sa.Column("external_id", sa.String(), nullable=False), sa.Column("stem", sa.Text(), nullable=False), sa.Column("normalized_stem", sa.Text(), nullable=False), sa.Column("stem_fingerprint", sa.String(), nullable=False), sa.Column("options", sa.JSON(), nullable=False), sa.Column("options_fingerprint", sa.String(), nullable=False), sa.Column("standard_answer", sa.String(), nullable=False), sa.Column("explanation", sa.Text(), nullable=False), sa.Column("knowledge_points", sa.JSON(), nullable=False), sa.Column("question_type", sa.String(), nullable=False), sa.Column("region", sa.String(), nullable=False), sa.Column("license_type", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=False), sa.UniqueConstraint("knowledge_version_id", "external_id"))
    for name in ("knowledge_version_id", "school_id", "stem_fingerprint", "options_fingerprint", "status"): op.create_index(f"ix_standard_questions_{name}", "standard_questions", [name])
    op.create_table("knowledge_chunks", sa.Column("id", sa.String(), primary_key=True), sa.Column("question_id", sa.String(), sa.ForeignKey("standard_questions.id"), nullable=False, unique=True), sa.Column("knowledge_version_id", sa.String(), sa.ForeignKey("knowledge_versions.id"), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("content_hash", sa.String(), nullable=False), sa.Column("embedding_status", sa.String(), nullable=False), sa.Column("vector_record_id", sa.String(), nullable=True))
    op.create_index("ix_knowledge_chunks_question_id", "knowledge_chunks", ["question_id"]); op.create_index("ix_knowledge_chunks_knowledge_version_id", "knowledge_chunks", ["knowledge_version_id"]); op.create_index("ix_knowledge_chunks_content_hash", "knowledge_chunks", ["content_hash"])
    op.create_table("knowledge_validation_issues", sa.Column("id", sa.String(), primary_key=True), sa.Column("knowledge_version_id", sa.String(), sa.ForeignKey("knowledge_versions.id"), nullable=False), sa.Column("external_id", sa.String(), nullable=True), sa.Column("row_number", sa.Integer(), nullable=True), sa.Column("issue_type", sa.String(), nullable=False), sa.Column("severity", sa.String(), nullable=False), sa.Column("safe_message", sa.Text(), nullable=False), sa.Column("status", sa.String(), nullable=False), sa.Column("resolution", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_knowledge_validation_issues_knowledge_version_id", "knowledge_validation_issues", ["knowledge_version_id"])
    op.create_table("retrieval_traces", sa.Column("id", sa.String(), primary_key=True), sa.Column("question_id", sa.String(), sa.ForeignKey("questions.id"), nullable=True), sa.Column("knowledge_version_id", sa.String(), sa.ForeignKey("knowledge_versions.id"), nullable=True), sa.Column("query_hash", sa.String(), nullable=False), sa.Column("match_type", sa.String(), nullable=False), sa.Column("candidate_ids", sa.JSON(), nullable=False), sa.Column("final_evidence_ids", sa.JSON(), nullable=False), sa.Column("error_code", sa.String(), nullable=True), sa.Column("latency_ms", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_retrieval_traces_question_id", "retrieval_traces", ["question_id"]); op.create_index("ix_retrieval_traces_query_hash", "retrieval_traces", ["query_hash"])


def downgrade():
    for table in ("retrieval_traces", "knowledge_validation_issues", "knowledge_chunks", "standard_questions", "knowledge_versions", "knowledge_sources"): op.drop_table(table)

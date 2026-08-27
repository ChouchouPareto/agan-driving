"""add staff ticket workflow

Revision ID: 27c2a310f321
Revises: 8a27b2c0d1e2
"""
from alembic import op
import sqlalchemy as sa

revision = "27c2a310f321"
down_revision = "8a27b2c0d1e2"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "staff" not in tables:
        op.create_table("staff", sa.Column("id", sa.String(), primary_key=True), sa.Column("display_name", sa.String(), nullable=False), sa.Column("school_id", sa.String(), nullable=False), sa.Column("role", sa.String(), nullable=False), sa.Column("session_token_hash", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_staff_school_id", "staff", ["school_id"])
        op.create_index("ix_staff_session_token_hash", "staff", ["session_token_hash"], unique=True)
    existing_columns = {column["name"] for column in inspector.get_columns("review_tickets")}
    with op.batch_alter_table("review_tickets") as batch:
        if "school_id" not in existing_columns: batch.add_column(sa.Column("school_id", sa.String(), nullable=False, server_default="pilot-school"))
        if "assignee_id" not in existing_columns: batch.add_column(sa.Column("assignee_id", sa.String(), nullable=True))
        if "version" not in existing_columns: batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        if "replied_at" not in existing_columns: batch.add_column(sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True))
        if "closed_at" not in existing_columns: batch.add_column(sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    existing_indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("review_tickets")}
    if "ix_review_tickets_school_id" not in existing_indexes: op.create_index("ix_review_tickets_school_id", "review_tickets", ["school_id"])
    if "ix_review_tickets_assignee_id" not in existing_indexes: op.create_index("ix_review_tickets_assignee_id", "review_tickets", ["assignee_id"])
    if "ticket_messages" not in tables:
        op.create_table("ticket_messages", sa.Column("id", sa.String(), primary_key=True), sa.Column("ticket_id", sa.String(), sa.ForeignKey("review_tickets.id"), nullable=False), sa.Column("author_type", sa.String(), nullable=False), sa.Column("author_id", sa.String(), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_ticket_messages_ticket_id", "ticket_messages", ["ticket_id"])
    if "ticket_events" not in tables:
        op.create_table("ticket_events", sa.Column("id", sa.String(), primary_key=True), sa.Column("ticket_id", sa.String(), sa.ForeignKey("review_tickets.id"), nullable=False), sa.Column("actor_type", sa.String(), nullable=False), sa.Column("actor_id", sa.String(), nullable=False), sa.Column("event_type", sa.String(), nullable=False), sa.Column("from_status", sa.String(), nullable=True), sa.Column("to_status", sa.String(), nullable=True), sa.Column("request_id", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_ticket_events_ticket_id", "ticket_events", ["ticket_id"])
        op.create_index("ix_ticket_events_request_id", "ticket_events", ["request_id"], unique=True)


def downgrade():
    op.drop_table("ticket_events")
    op.drop_table("ticket_messages")
    with op.batch_alter_table("review_tickets") as batch:
        batch.drop_index("ix_review_tickets_assignee_id")
        batch.drop_index("ix_review_tickets_school_id")
        batch.drop_constraint("fk_review_tickets_assignee", type_="foreignkey")
        for name in ("closed_at", "replied_at", "version", "assignee_id", "school_id"):
            batch.drop_column(name)
    op.drop_table("staff")

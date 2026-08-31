"""add persistent chunk embeddings

Revision ID: d4c9f3a7b812
Revises: b73d9012f5aa
Create Date: 2026-08-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4c9f3a7b812"
down_revision: Union[str, None] = "b73d9012f5aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_chunks", sa.Column("embedding", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_chunks", "embedding")

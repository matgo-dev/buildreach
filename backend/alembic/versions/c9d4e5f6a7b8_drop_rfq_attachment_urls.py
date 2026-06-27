"""drop rfq attachment_urls

Revision ID: c9d4e5f6a7b8
Revises: a84ca1ab6928
Create Date: 2026-06-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d4e5f6a7b8"
down_revision: Union[str, None] = "a84ca1ab6928"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("rfqs", "attachment_urls")


def downgrade() -> None:
    op.add_column(
        "rfqs",
        sa.Column("attachment_urls", sa.JSON(), nullable=True),
    )

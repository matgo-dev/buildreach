"""feat(rfq): alter required_certifications and attachment_urls from Text to JSON

Revision ID: f2e83cdfe399
Revises: 2e3ee5b1066c
Create Date: 2026-06-10 14:05:29.519796
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2e83cdfe399'
down_revision: Union[str, None] = '2e3ee5b1066c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'rfqs', 'required_certifications',
        existing_type=sa.TEXT(),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using='required_certifications::json',
    )
    op.alter_column(
        'rfqs', 'attachment_urls',
        existing_type=sa.TEXT(),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using='attachment_urls::json',
    )


def downgrade() -> None:
    op.alter_column(
        'rfqs', 'attachment_urls',
        existing_type=sa.JSON(),
        type_=sa.TEXT(),
        existing_nullable=True,
    )
    op.alter_column(
        'rfqs', 'required_certifications',
        existing_type=sa.JSON(),
        type_=sa.TEXT(),
        existing_nullable=True,
    )

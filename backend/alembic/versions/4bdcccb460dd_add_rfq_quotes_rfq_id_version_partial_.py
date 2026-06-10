"""add rfq_quotes (rfq_id, version) partial unique index

Revision ID: 4bdcccb460dd
Revises: f2e83cdfe399
Create Date: 2026-06-10 16:51:31.391694
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4bdcccb460dd'
down_revision: Union[str, None] = 'f2e83cdfe399'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'uq_rfq_quotes_rfq_version_active',
        'rfq_quotes',
        ['rfq_id', 'version'],
        unique=True,
        postgresql_where='deleted_at IS NULL',
    )


def downgrade() -> None:
    op.drop_index(
        'uq_rfq_quotes_rfq_version_active',
        table_name='rfq_quotes',
        postgresql_where='deleted_at IS NULL',
    )

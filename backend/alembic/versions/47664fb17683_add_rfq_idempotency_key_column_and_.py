"""add rfq idempotency_key column and partial unique index

Revision ID: 47664fb17683
Revises: 4bdcccb460dd
Create Date: 2026-06-11 11:24:58.745550
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47664fb17683'
down_revision: Union[str, None] = '4bdcccb460dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rfqs', sa.Column('idempotency_key', sa.String(length=255), nullable=True))
    op.create_index(
        'uq_rfqs_idem_key_active', 'rfqs',
        ['created_by_user_id', 'idempotency_key'],
        unique=True,
        postgresql_where='idempotency_key IS NOT NULL AND deleted_at IS NULL',
    )


def downgrade() -> None:
    op.drop_index(
        'uq_rfqs_idem_key_active', table_name='rfqs',
        postgresql_where='idempotency_key IS NOT NULL AND deleted_at IS NULL',
    )
    op.drop_column('rfqs', 'idempotency_key')

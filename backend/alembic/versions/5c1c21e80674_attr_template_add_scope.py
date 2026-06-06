"""attr_template_add_scope

Revision ID: 5c1c21e80674
Revises: 20260606_attr_sku
Create Date: 2026-06-06 21:41:04.635978
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c1c21e80674'
down_revision: Union[str, None] = '20260606_attr_sku'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('attr_templates', sa.Column('scope', sa.String(length=3), server_default='SKU', nullable=False))


def downgrade() -> None:
    op.drop_column('attr_templates', 'scope')

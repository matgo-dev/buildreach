"""product_add_manufacturer_model

Revision ID: e36a9e44d149
Revises: 5d30666e77ed
Create Date: 2026-06-28 13:01:31.281053
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e36a9e44d149'
down_revision: Union[str, None] = '5d30666e77ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('manufacturer_model', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'manufacturer_model')

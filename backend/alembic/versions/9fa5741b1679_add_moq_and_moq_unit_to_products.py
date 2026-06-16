"""add moq and moq_unit to products

Revision ID: 9fa5741b1679
Revises: 1c9a56723713
Create Date: 2026-06-13 10:18:35.726423
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9fa5741b1679'
down_revision: Union[str, None] = '1c9a56723713'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('moq', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('moq_unit', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'moq_unit')
    op.drop_column('products', 'moq')

"""add translation_glossary table

Revision ID: 9e56690ae8cc
Revises: 972105986ecc
Create Date: 2026-06-04 16:50:38.445614
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9e56690ae8cc'
down_revision: Union[str, None] = '972105986ecc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('translation_glossary',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_locale', sa.String(length=10), nullable=False),
        sa.Column('target_locale', sa.String(length=10), nullable=False),
        sa.Column('source_term', sa.String(length=200), nullable=False),
        sa.Column('target_term', sa.String(length=200), nullable=False),
        sa.Column('domain', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('translation_glossary')

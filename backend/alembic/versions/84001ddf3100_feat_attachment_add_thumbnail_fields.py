"""feat(attachment): add thumbnail fields

Revision ID: 84001ddf3100
Revises: b4cc274a0786
Create Date: 2026-06-21 13:31:57.444505
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '84001ddf3100'
down_revision: Union[str, None] = 'b4cc274a0786'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('attachments', sa.Column('thumbnail_key', sa.String(length=300), nullable=True))
    op.add_column('attachments', sa.Column('thumbnail_content_type', sa.String(length=50), nullable=True))
    op.add_column('attachments', sa.Column('thumbnail_size_bytes', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('attachments', 'thumbnail_size_bytes')
    op.drop_column('attachments', 'thumbnail_content_type')
    op.drop_column('attachments', 'thumbnail_key')

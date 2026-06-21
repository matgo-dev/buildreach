"""add quote_documents table

Revision ID: a00ab037065f
Revises: 84001ddf3100
Create Date: 2026-06-21 14:07:28.583915
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a00ab037065f'
down_revision: Union[str, None] = '84001ddf3100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('quote_documents',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('quote_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('locale', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('storage_key', sa.String(length=500), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('retry_count', sa.Integer(), nullable=False),
    sa.Column('generated_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['quote_id'], ['rfq_quotes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('quote_id', 'version', 'locale', name='uq_quote_doc_version_locale')
    )
    op.create_index('ix_quote_documents_quote_id', 'quote_documents', ['quote_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_quote_documents_quote_id', table_name='quote_documents')
    op.drop_table('quote_documents')

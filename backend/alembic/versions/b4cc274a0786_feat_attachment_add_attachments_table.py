"""feat_attachment_add_attachments_table

Revision ID: b4cc274a0786
Revises: bdf9c2192003
Create Date: 2026-06-21 09:55:10.625061
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4cc274a0786'
down_revision: Union[str, None] = 'bdf9c2192003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('attachments',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('file_key', sa.String(length=300), nullable=False),
    sa.Column('original_filename', sa.String(length=500), nullable=False),
    sa.Column('content_type', sa.String(length=200), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('uploaded_by_user_id', sa.Integer(), nullable=False),
    sa.Column('owner_type', sa.String(length=20), nullable=True),
    sa.Column('owner_id', sa.Integer(), nullable=True),
    sa.Column('first_linked_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.CheckConstraint("owner_type IS NULL OR owner_type IN ('RFQ', 'QUOTE')", name='ck_attachments_owner_type_enum'),
    sa.CheckConstraint('(owner_type IS NULL AND owner_id IS NULL) OR (owner_type IS NOT NULL AND owner_id IS NOT NULL)', name='ck_attachments_owner_sync'),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_attachments_deleted_by'),
    sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id'], name='fk_attachments_uploaded_by'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('file_key')
    )
    op.create_index(op.f('ix_attachments_deleted_at'), 'attachments', ['deleted_at'], unique=False)
    op.create_index('ix_attachments_owner', 'attachments', ['owner_type', 'owner_id', 'deleted_at'], unique=False)
    op.create_index('ix_attachments_uploaded_by', 'attachments', ['uploaded_by_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_attachments_uploaded_by', table_name='attachments')
    op.drop_index('ix_attachments_owner', table_name='attachments')
    op.drop_index(op.f('ix_attachments_deleted_at'), table_name='attachments')
    op.drop_table('attachments')

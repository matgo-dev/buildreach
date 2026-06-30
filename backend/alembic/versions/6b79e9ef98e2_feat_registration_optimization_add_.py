"""feat: registration optimization - add whatsapp, deactivated status, verification_codes table

Revision ID: 6b79e9ef98e2
Revises: f1a2b3c4d5e6
Create Date: 2026-06-29 18:28:19.309990
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6b79e9ef98e2'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('products', 'ref_price_tiers',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               type_=sa.JSON(),
               existing_nullable=True)
    op.add_column('users', sa.Column('whatsapp', sa.String(length=30), nullable=True))
    op.create_table('verification_codes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('purpose', sa.String(length=20), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('used', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_vc_email_purpose', 'verification_codes', ['email', 'purpose'], unique=False)
    op.create_index(op.f('ix_verification_codes_email'), 'verification_codes', ['email'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_verification_codes_email'), table_name='verification_codes')
    op.drop_index('ix_vc_email_purpose', table_name='verification_codes')
    op.drop_table('verification_codes')
    op.drop_column('users', 'whatsapp')
    op.alter_column('products', 'ref_price_tiers',
               existing_type=sa.JSON(),
               type_=postgresql.JSONB(astext_type=sa.Text()),
               existing_nullable=True)
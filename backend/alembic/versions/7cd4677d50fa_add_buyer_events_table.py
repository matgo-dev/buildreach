"""add buyer_events table

Revision ID: 7cd4677d50fa
Revises: d087cf2f6c5b
Create Date: 2026-06-17 11:08:30.891802
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7cd4677d50fa'
down_revision: Union[str, None] = 'd087cf2f6c5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('buyer_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('buyer_org_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.String(length=36), nullable=True),
    sa.Column('event_type', sa.String(length=30), nullable=False),
    sa.Column('resource_type', sa.String(length=30), nullable=True),
    sa.Column('resource_id', sa.Integer(), nullable=True),
    sa.Column('referrer', sa.String(length=500), nullable=True),
    sa.Column('device_type', sa.String(length=20), nullable=True),
    sa.Column('ip', sa.String(length=50), nullable=True),
    sa.Column('extra', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['buyer_org_id'], ['buyer_organizations.id'], name='fk_buyer_events_org_id'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_buyer_events_user_id'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_buyer_events_created_at', 'buyer_events', ['created_at'], unique=False)
    op.create_index('ix_buyer_events_org_time', 'buyer_events', ['buyer_org_id', 'created_at'], unique=False)
    op.create_index('ix_buyer_events_resource', 'buyer_events', ['resource_type', 'resource_id'], unique=False)
    op.create_index('ix_buyer_events_session', 'buyer_events', ['session_id'], unique=False)
    op.create_index('ix_buyer_events_user_time', 'buyer_events', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_buyer_events_user_type_time', 'buyer_events', ['user_id', 'event_type', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_buyer_events_user_type_time', table_name='buyer_events')
    op.drop_index('ix_buyer_events_user_time', table_name='buyer_events')
    op.drop_index('ix_buyer_events_session', table_name='buyer_events')
    op.drop_index('ix_buyer_events_resource', table_name='buyer_events')
    op.drop_index('ix_buyer_events_org_time', table_name='buyer_events')
    op.drop_index('ix_buyer_events_created_at', table_name='buyer_events')
    op.drop_table('buyer_events')

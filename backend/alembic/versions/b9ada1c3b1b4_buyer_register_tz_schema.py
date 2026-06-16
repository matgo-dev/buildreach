"""buyer_register_tz_schema

Revision ID: b9ada1c3b1b4
Revises: b3c4d5e6f7g8
Create Date: 2026-06-15 22:41:39.722569

变更:
- users.email 改为 nullable (邮箱选填)
- buyer_organizations 加列: address / tin / brela_no / business_category_codes
- 新建表 buyer_browse_preferences (浏览偏好, user 1:1)
- 新建表 buyer_org_images (门店照片 + 证照)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b9ada1c3b1b4'
down_revision: Union[str, None] = 'b3c4d5e6f7g8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users.email 改 nullable
    op.alter_column('users', 'email',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)

    # 2. buyer_organizations 加坦桑场景字段
    op.add_column('buyer_organizations', sa.Column('address', sa.String(length=255), nullable=True))
    op.add_column('buyer_organizations', sa.Column('tin', sa.String(length=50), nullable=True))
    op.add_column('buyer_organizations', sa.Column('brela_no', sa.String(length=50), nullable=True))
    op.add_column('buyer_organizations', sa.Column('business_category_codes', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))

    # 3. 新建 buyer_browse_preferences
    op.create_table('buyer_browse_preferences',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('category_codes', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_buyer_browse_preferences_user_id'), 'buyer_browse_preferences', ['user_id'], unique=True)

    # 4. 新建 buyer_org_images
    op.create_table('buyer_org_images',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('buyer_org_id', sa.Integer(), nullable=False),
    sa.Column('image_key', sa.String(length=300), nullable=False),
    sa.Column('image_type', sa.String(length=20), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['buyer_org_id'], ['buyer_organizations.id'], name='fk_buyer_org_images_org_id', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_buyer_org_images_deleted_by'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_buyer_org_images_deleted_at'), 'buyer_org_images', ['deleted_at'], unique=False)
    op.create_index('ix_buyer_org_images_org_id', 'buyer_org_images', ['buyer_org_id'], unique=False)
    op.create_index('ix_buyer_org_images_type', 'buyer_org_images', ['buyer_org_id', 'image_type'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_buyer_org_images_type', table_name='buyer_org_images')
    op.drop_index('ix_buyer_org_images_org_id', table_name='buyer_org_images')
    op.drop_index(op.f('ix_buyer_org_images_deleted_at'), table_name='buyer_org_images')
    op.drop_table('buyer_org_images')

    op.drop_index(op.f('ix_buyer_browse_preferences_user_id'), table_name='buyer_browse_preferences')
    op.drop_table('buyer_browse_preferences')

    op.drop_column('buyer_organizations', 'business_category_codes')
    op.drop_column('buyer_organizations', 'brela_no')
    op.drop_column('buyer_organizations', 'tin')
    op.drop_column('buyer_organizations', 'address')

    op.alter_column('users', 'email',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)

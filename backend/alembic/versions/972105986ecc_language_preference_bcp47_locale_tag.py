"""language_preference_bcp47_locale_tag

Revision ID: 972105986ecc
Revises: bf635112740a
Create Date: 2026-06-04 10:20:35.260178

列宽 VARCHAR(10) → VARCHAR(35) + 既有裸 ISO 639-1 码回填为 BCP 47 locale tag。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '972105986ecc'
down_revision: Union[str, None] = 'bf635112740a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 语言到国家 1:1 的确定映射（不含 ar,ar 需 join 组织表）
_DETERMINISTIC_MAP = {
    "zh": "zh-CN",
    "km": "km-KH",
    "ur": "ur-PK",
    "id": "id-ID",
    "ms": "ms-MY",
    # en → en 无需改
}


def upgrade() -> None:
    # 1. 列宽放宽（widening，安全操作）
    op.alter_column(
        "users",
        "language_preference",
        existing_type=sa.String(10),
        type_=sa.String(35),
        existing_nullable=True,
    )

    # 2. 回填 1:1 确定映射
    users = sa.table("users", sa.column("language_preference", sa.String))
    for old, new in _DETERMINISTIC_MAP.items():
        op.execute(
            users.update()
            .where(users.c.language_preference == old)
            .values(language_preference=new)
        )

    # 3. ar 行：经 supplier_members → supplier_organizations 取 country_code
    #    置为 ar-{country_code}（如 ar-MA、ar-IQ、ar-SA、ar-AE）
    op.execute(sa.text("""
        UPDATE users u
        SET language_preference = 'ar-' || so.country_code
        FROM supplier_members sm
        JOIN supplier_organizations so ON so.id = sm.supplier_org_id
        WHERE u.id = sm.user_id
          AND u.language_preference = 'ar'
    """))

    # 4. 安全检查：如果还有残留的裸 ar（无组织关联），抛异常而非静默写脏值
    conn = op.get_bind()
    remaining = conn.execute(
        sa.text("SELECT id FROM users WHERE language_preference = 'ar' LIMIT 1")
    ).fetchone()
    if remaining:
        raise RuntimeError(
            f"回填失败：user.id={remaining[0]} language_preference='ar' 但无法通过 "
            "supplier_members/supplier_organizations join 解析 country_code，请人工处理"
        )


def downgrade() -> None:
    # 列宽缩回（回填不反向，tag 值会被截断但 downgrade 本身是应急操作）
    op.alter_column(
        "users",
        "language_preference",
        existing_type=sa.String(35),
        type_=sa.String(10),
        existing_nullable=True,
    )

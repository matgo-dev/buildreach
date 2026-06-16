"""phone_e164_data_migration

存量手机号归一化为 E.164 格式。
- 裸 11 位 1 开头 → CN → +86…
- 坦桑本地格式 → TZ → +255…
- 已 +开头且合法 → 不动
- 冲突/脏号 → 打印清单,不中断

Revision ID: 7e858d97bff2
Revises: b9ada1c3b1b4
Create Date: 2026-06-16 13:14:59.620451
"""
from typing import Sequence, Union

import logging
from alembic import op
import sqlalchemy as sa

revision: str = '7e858d97bff2'
down_revision: Union[str, None] = 'b9ada1c3b1b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)


def _normalize(raw: str) -> str | None:
    """尝试归一化手机号,失败返回 None。"""
    import phonenumbers
    phone = raw.strip()
    if not phone:
        return None

    # 猜测 region
    region = None
    if phone.startswith("+"):
        region = None  # phonenumbers 会从 + 前缀自动识别
    elif phone.isdigit() and len(phone) == 11 and phone.startswith("1"):
        region = "CN"
    elif phone.startswith("0") and len(phone) == 10:
        region = "TZ"
    elif phone.startswith("255"):
        region = "TZ"
    elif phone.isdigit() and len(phone) == 9:
        region = "TZ"  # 坦桑无前缀

    try:
        num = phonenumbers.parse(phone, region)
        if phonenumbers.is_valid_number(num):
            return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    return None


def upgrade() -> None:
    conn = op.get_bind()
    users = sa.table("users", sa.column("id", sa.Integer), sa.column("phone", sa.String))

    rows = conn.execute(sa.select(users.c.id, users.c.phone).where(users.c.phone.isnot(None))).fetchall()

    updated = 0
    conflicts: list[tuple[int, str, str]] = []
    dirty: list[tuple[int, str]] = []

    # 收集所有现有 E.164 号码用于冲突检测
    existing_phones: dict[str, int] = {}
    for uid, phone in rows:
        if phone and phone.startswith("+"):
            existing_phones[phone] = uid

    for uid, phone in rows:
        if not phone:
            continue

        e164 = _normalize(phone)
        if e164 is None:
            dirty.append((uid, phone))
            continue

        if e164 == phone:
            # 已是 E.164,只注册到 existing_phones
            existing_phones.setdefault(e164, uid)
            continue

        # 检查冲突
        if e164 in existing_phones and existing_phones[e164] != uid:
            conflicts.append((uid, phone, e164))
            continue

        # 更新
        conn.execute(users.update().where(users.c.id == uid).values(phone=e164))
        existing_phones[e164] = uid
        updated += 1

    if conflicts:
        logger.warning(
            "Phone E.164 migration: %d CONFLICTS (需人工合并):\n%s",
            len(conflicts),
            "\n".join(f"  user_id={uid} raw={raw} → e164={e164}" for uid, raw, e164 in conflicts),
        )
    if dirty:
        logger.warning(
            "Phone E.164 migration: %d DIRTY (无法归一化):\n%s",
            len(dirty),
            "\n".join(f"  user_id={uid} phone={phone}" for uid, phone in dirty),
        )
    logger.info("Phone E.164 migration: %d updated, %d conflicts, %d dirty", updated, len(conflicts), len(dirty))


def downgrade() -> None:
    # 不可逆:E.164 → 原始格式无法还原
    pass

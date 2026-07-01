"""平台商品编码生成。

对外展示平台自有 code，来源平台原始编号只作为 HMAC 输入，不出现在 code 中。
"""
from __future__ import annotations

import hashlib
import hmac

from app.core.config import settings

CODE_HASH_LENGTH = 12


def _code_secret() -> str:
    """返回编码密钥。生产可用 CODE_HASH_SECRET 与 JWT_SECRET_KEY 解耦。"""
    return settings.CODE_HASH_SECRET or settings.JWT_SECRET_KEY


def _hmac_prefix(identity: str, *, length: int = CODE_HASH_LENGTH) -> str:
    digest = hmac.new(
        _code_secret().encode("utf-8"),
        identity.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:length].upper()


def xfs_product_code(xfs_spu_code: str | int) -> str:
    """XFS SPU 原始编号 → 平台 SPU code。"""
    raw = str(xfs_spu_code).strip()
    return f"MG-P{_hmac_prefix(f'P:XFS:{raw}')}"


def xfs_sku_code(xfs_sku_code: str | int) -> str:
    """XFS SKU 原始编号 → 平台 SKU code。"""
    raw = str(xfs_sku_code).strip()
    return f"MG-S{_hmac_prefix(f'S:XFS:{raw}')}"

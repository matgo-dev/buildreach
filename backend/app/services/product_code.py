"""平台商品编码生成。

对外展示平台自有 code，来源平台原始编号只作为稳定 hash 输入，不出现在 code 中。
"""
from __future__ import annotations

import hashlib

CODE_HASH_LENGTH = 12


def _hash_prefix(identity: str, *, length: int = CODE_HASH_LENGTH) -> str:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return digest[:length].upper()


def xfs_product_code(xfs_spu_code: str | int) -> str:
    """XFS SPU 原始编号 → 平台 SPU code。"""
    raw = str(xfs_spu_code).strip()
    return f"MG-P{_hash_prefix(f'P:XFS:{raw}')}"


def xfs_sku_code(xfs_sku_code: str | int) -> str:
    """XFS SKU 原始编号 → 平台 SKU code。"""
    raw = str(xfs_sku_code).strip()
    return f"MG-S{_hash_prefix(f'S:XFS:{raw}')}"

"""平台商品编码生成。

统一规则(2026-07-03 定盘):
    platformSpuCode = "MG-P" + SHA256("P:<来源>:<来源原始编号>") 十六进制前 12 位大写
    platformSkuCode = "MG-S" + SHA256("S:<来源>:<来源原始编号>") 十六进制前 12 位大写

- 对外只展示平台自有 code;来源平台名与原始编号只作 hash 输入,不出现在 code 里(不泄露货源)。
- 自建商品也走 MG-P:把它当一个"来源"(如 ZSOE 材料表),hash 输入用其**不可变**稳定键。
"""
from __future__ import annotations

import hashlib

CODE_HASH_LENGTH = 12


def _hash_prefix(identity: str, *, length: int = CODE_HASH_LENGTH) -> str:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return digest[:length].upper()


def platform_spu_code(source: str, source_code: str) -> str:
    """来源 source 的原始 SPU 编号 → 平台中性 SPU code(MG-P + SHA256('P:source:code')[:12])。"""
    return f"MG-P{_hash_prefix(f'P:{source}:{str(source_code).strip()}')}"


def platform_sku_code(source: str, source_code: str) -> str:
    """来源 source 的原始 SKU 编号 → 平台中性 SKU code(MG-S + SHA256('S:source:code')[:12])。"""
    return f"MG-S{_hash_prefix(f'S:{source}:{str(source_code).strip()}')}"


def xfs_product_code(xfs_spu_code: str | int) -> str:
    """XFS SPU 原始编号 → 平台 SPU code(= platform_spu_code('XFS', ...),输出与历史一致)。"""
    return platform_spu_code("XFS", xfs_spu_code)


def xfs_sku_code(xfs_sku_code: str | int) -> str:
    """XFS SKU 原始编号 → 平台 SKU code(= platform_sku_code('XFS', ...),输出与历史一致)。"""
    return platform_sku_code("XFS", xfs_sku_code)

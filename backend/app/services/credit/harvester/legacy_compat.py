"""raw_data.evidence 格式兼容访问器(Δ7 v0.3)。

v0.2 落库:evidence = {field: "quote 字符串"}
v0.3 落库:evidence = {field: {quote, source_index, source_url}}

读取侧统一用本模块归一化,**不强制迁移历史数据**。
"""
from __future__ import annotations

from typing import Any

_EMPTY = {"quote": None, "source_index": None, "source_url": None}


def normalize_field_evidence(value: Any) -> dict[str, Any]:
    """把单字段 evidence 归一成 {quote, source_index, source_url} 对象。

    - v0.3 dict → 补齐三键
    - v0.2 字符串 → {quote: 该字符串, source_index: None, source_url: None}
    - None / 其他 → 全 None
    """
    if isinstance(value, str):
        return {"quote": value, "source_index": None, "source_url": None}
    if isinstance(value, dict):
        return {
            "quote": value.get("quote"),
            "source_index": value.get("source_index"),
            "source_url": value.get("source_url"),
        }
    return dict(_EMPTY)


def get_evidence_map(raw_data: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """从一条快照的 raw_data 取出归一化 evidence map(v0.2/v0.3 通吃)。"""
    if not raw_data:
        return {}
    evidence = raw_data.get("evidence") or {}
    return {field: normalize_field_evidence(v) for field, v in evidence.items()}

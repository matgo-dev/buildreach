"""resolve_purchase_target() 纯决策逻辑单测(_decide_target / _variants_to_map)。

不连库，只喂轻量假对象，验证 SKU 解析的分支：
零 SKU / 单默认 SKU / 多 SKU 需 variants 消歧 / 唯一解析 / 显式 sku_id 与 variants 不一致拒绝。

variant_snapshot 落库口径沿用既有约定 {"attr_name", "value"}（见 app/services/_variant_utils.py），
selected_variants 输入兼容 {"attr_name","value"} / {"attr_key_en","attr_value_en"} / {"key","value"} 三种形状。
"""
from __future__ import annotations

import pytest

from app.services.purchase_target import (
    SkuMismatchError,
    VariantUnresolvableError,
    _decide_target,
    _snapshot_of,
    _variants_to_map,
)


class _Attr:
    def __init__(self, key: str, value: str, selectable: bool = True):
        self.attr_key_en = key
        self.attr_value_en = value
        self.selectable = selectable


class _S:
    """假 ProductSku：tuple= 规格字典 -> 转成 selectable attrs 挂在 .attrs 上。"""

    def __init__(self, id, tuple=None, is_default=False):
        self.id = id
        self.is_default = is_default
        self.attrs = [_Attr(k, v) for k, v in (tuple or {}).items()]


class _P:
    def __init__(self, visibility="PUBLIC"):
        self.visibility = visibility


def test_simple_product_zero_sku_allows_null():
    prod = _P(visibility="PUBLIC")
    sku_id, snap = _decide_target(prod, active_skus=[], selected_variants=[], sku_id=None)
    assert sku_id is None
    assert snap == []


def test_single_default_sku_binds_it():
    prod = _P(visibility="PUBLIC")
    sku_id, snap = _decide_target(
        prod, active_skus=[_S(id=7, is_default=True, tuple={})], selected_variants=[], sku_id=None
    )
    assert sku_id == 7


def test_multi_sku_requires_variants_else_reject():
    prod = _P()
    skus = [_S(id=1, tuple={"spec": "A"}), _S(id=2, tuple={"spec": "B"})]
    with pytest.raises(VariantUnresolvableError):
        _decide_target(prod, active_skus=skus, selected_variants=[], sku_id=None)


def test_multi_sku_resolves_unique():
    prod = _P()
    skus = [_S(id=1, tuple={"spec": "A"}), _S(id=2, tuple={"spec": "B"})]
    sku_id, snap = _decide_target(
        prod, active_skus=skus, selected_variants=[{"attr_name": "spec", "value": "B"}], sku_id=None
    )
    assert sku_id == 2
    assert snap == [{"attr_name": "spec", "value": "B"}]


def test_multi_sku_ambiguous_variants_reject():
    """selected_variants 命中不到唯一 SKU(此处命中 0 个)必须拒绝，不允许静默挑一个。"""
    prod = _P()
    skus = [_S(id=1, tuple={"spec": "A"}), _S(id=2, tuple={"spec": "B"})]
    with pytest.raises(VariantUnresolvableError):
        _decide_target(
            prod, active_skus=skus, selected_variants=[{"attr_name": "spec", "value": "C"}], sku_id=None
        )


def test_passed_sku_id_mismatch_variants_raises():
    prod = _P()
    skus = [_S(id=1, tuple={"spec": "A"})]
    with pytest.raises(SkuMismatchError):
        _decide_target(
            prod, active_skus=skus, selected_variants=[{"attr_name": "spec", "value": "B"}], sku_id=1
        )


def test_passed_sku_id_not_in_active_skus_raises():
    """sku_id 传了但不在 active_skus 里(已下架/不属于该商品)必须拒绝。"""
    prod = _P()
    skus = [_S(id=1, tuple={"spec": "A"})]
    with pytest.raises(SkuMismatchError):
        _decide_target(prod, active_skus=skus, selected_variants=[], sku_id=999)


def test_passed_sku_id_matches_variants_ok():
    prod = _P()
    skus = [_S(id=1, tuple={"spec": "A"})]
    sku_id, snap = _decide_target(
        prod, active_skus=skus, selected_variants=[{"attr_name": "spec", "value": "A"}], sku_id=1
    )
    assert sku_id == 1
    assert snap == [{"attr_name": "spec", "value": "A"}]


def test_variants_to_map_accepts_multiple_shapes():
    """兼容既有口径 attr_name/value，以及 attr_key_en/attr_value_en、key/value 三种输入形状。"""
    assert _variants_to_map([{"attr_name": "spec", "value": "A"}]) == {"spec": "A"}
    assert _variants_to_map([{"attr_key_en": "spec", "attr_value_en": "A"}]) == {"spec": "A"}
    assert _variants_to_map([{"key": "spec", "value": "A"}]) == {"spec": "A"}
    assert _variants_to_map(None) == {}
    assert _variants_to_map([]) == {}


def test_snapshot_of_sorts_deterministically():
    """_snapshot_of 必须按 (attr_name, value) 排序，使 variant_fingerprint() 产生一致的哈希。

    输入 tuple_map 的迭代顺序不保证，但输出 snapshot 必须始终排序一致。
    本测试用 2 个属性故意反序传入，验证输出已排序。
    """
    # 反序输入：先 "size": "L"，再 "color": "Red"
    tuple_map = {"size": "L", "color": "Red"}
    snapshot = _snapshot_of(tuple_map)

    # 验证输出已按 (attr_name, value) 排序
    # "color": "Red" 应排在 "size": "L" 前（色< 尺size）
    assert snapshot == [
        {"attr_name": "color", "value": "Red"},
        {"attr_name": "size", "value": "L"},
    ]


def test_multi_sku_ambiguous_two_matches_raise_error():
    """数据异常：两个 SKU 拥有相同的 selectable-attr 组合（规格冲突）。
    selected_variants 本应唯一命中，但命中了 2 个，必须拒绝，不允许静默挑一个。
    """
    prod = _P()
    # 两个 SKU，都有完全相同的规格 {"spec": "A"}
    skus = [_S(id=1, tuple={"spec": "A"}), _S(id=2, tuple={"spec": "A"})]
    with pytest.raises(VariantUnresolvableError) as exc_info:
        _decide_target(
            prod, active_skus=skus, selected_variants=[{"attr_name": "spec", "value": "A"}], sku_id=None
        )
    # 错误消息应包含匹配数目
    assert "2 skus" in str(exc_info.value)

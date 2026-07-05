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


def test_single_sku_snapshot_derived_from_sku_not_input():
    """单 SKU 有 selectable attr:列表路径(空输入)、详情路径(sku_id)、详情路径(variants)
    必须产出同一 (sku_id, snapshot) —— 快照从解析到的 SKU 算,不从入参透传。

    这是"同商品从列表加和从详情加产生两条篮子记录"bug 的根因契约:
    三条入口指纹一致 → 合并同一行。旧实现的单 SKU 分支透传 selected_variants,
    列表路径快照为 []、详情路径快照为 SKU attrs,两者指纹不同 → 双行。
    """
    prod = _P()
    sku = _S(id=5, tuple={"spec": "phi6"}, is_default=True)
    expect = (5, [{"attr_name": "spec", "value": "phi6"}])

    # 列表路径:完全空输入(allow_spu_level 不影响,单 SKU 直接绑)
    a = _decide_target(prod, active_skus=[sku], selected_variants=[], sku_id=None, allow_spu_level=True)
    # 详情路径:显式 sku_id,不带 variants
    b = _decide_target(prod, active_skus=[sku], selected_variants=[], sku_id=5)
    # 详情路径:带 variants
    c = _decide_target(
        prod, active_skus=[sku], selected_variants=[{"attr_name": "spec", "value": "phi6"}], sku_id=None
    )
    assert a == b == c == expect


def test_multi_sku_no_selection_binds_default_sku():
    """多 SKU 但设了 is_default:未选规格的加购(列表页)解析到默认 SKU,
    而非落 sku_id=NULL 泛询价行。这样"列表加默认 == 详情选默认" → 合并同一行。
    """
    prod = _P()
    skus = [
        _S(id=1, tuple={"spec": "phi6"}, is_default=True),
        _S(id=2, tuple={"spec": "phi8"}),
    ]
    sku_id, snap = _decide_target(
        prod, active_skus=skus, selected_variants=[], sku_id=None, allow_spu_level=True,
    )
    assert sku_id == 1
    assert snap == [{"attr_name": "spec", "value": "phi6"}]


def test_multi_sku_default_binds_even_without_spu_level_flag():
    """有 default 就是"有明确答案",无论 allow_spu_level 与否都绑 default,不报错。
    allow_spu_level 只在"多 SKU 且无 default"时才决定是泛询价还是拒绝。
    """
    prod = _P()
    skus = [
        _S(id=1, tuple={"spec": "phi6"}, is_default=True),
        _S(id=2, tuple={"spec": "phi8"}),
    ]
    sku_id, snap = _decide_target(
        prod, active_skus=skus, selected_variants=[], sku_id=None, allow_spu_level=False,
    )
    assert sku_id == 1
    assert snap == [{"attr_name": "spec", "value": "phi6"}]


def test_multi_sku_requires_variants_else_reject():
    prod = _P()
    skus = [_S(id=1, tuple={"spec": "A"}), _S(id=2, tuple={"spec": "B"})]
    with pytest.raises(VariantUnresolvableError):
        _decide_target(prod, active_skus=skus, selected_variants=[], sku_id=None)


def test_multi_sku_no_selection_allowed_when_spu_level_flag_set():
    """allow_spu_level=True + 空 selected_variants → 整 SPU 交易，放行为 (None, [])。

    这是购物车/询价单既有"整 SPU 加购/询价"流程的兼容口子(Task 7 §A)：
    只放宽"完全未选择"这一种情况，不改变其它任何拒绝分支。
    """
    prod = _P()
    skus = [_S(id=1, tuple={"spec": "A"}), _S(id=2, tuple={"spec": "B"})]
    sku_id, snap = _decide_target(
        prod, active_skus=skus, selected_variants=[], sku_id=None, allow_spu_level=True,
    )
    assert sku_id is None
    assert snap == []


def test_multi_sku_no_selection_still_rejects_when_flag_not_set():
    """同上场景，allow_spu_level=False(默认)时仍必须拒绝 —— 确认 flag 是显式开关。"""
    prod = _P()
    skus = [_S(id=1, tuple={"spec": "A"}), _S(id=2, tuple={"spec": "B"})]
    with pytest.raises(VariantUnresolvableError):
        _decide_target(
            prod, active_skus=skus, selected_variants=[], sku_id=None, allow_spu_level=False,
        )


def test_multi_sku_ambiguous_selection_still_rejects_even_with_spu_level_flag():
    """allow_spu_level=True 只放宽"未提供选择"，不放宽"提供了但解析不到唯一 SKU"
    (0 或 >1 匹配)——那是真实错误，不是整 SPU 语义，必须继续拒绝。
    """
    prod = _P()
    skus = [_S(id=1, tuple={"spec": "A"}), _S(id=2, tuple={"spec": "B"})]
    # 0 匹配
    with pytest.raises(VariantUnresolvableError):
        _decide_target(
            prod, active_skus=skus,
            selected_variants=[{"attr_name": "spec", "value": "C"}],
            sku_id=None, allow_spu_level=True,
        )
    # >1 匹配（数据异常：两个 SKU 规格相同）
    skus_dup = [_S(id=1, tuple={"spec": "A"}), _S(id=2, tuple={"spec": "A"})]
    with pytest.raises(VariantUnresolvableError):
        _decide_target(
            prod, active_skus=skus_dup,
            selected_variants=[{"attr_name": "spec", "value": "A"}],
            sku_id=None, allow_spu_level=True,
        )


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


# ─────────────────────────────────────────────────────────────────────────────
# default_sku_variant_display() —— 默认 SKU 规格展示串(直询预览用)
# 挑默认 SKU 的规则须与 _decide_target 分支 2 一致;展示口径须与 cart 的 variant_display 一致。
# ─────────────────────────────────────────────────────────────────────────────
from app.db.models.product_sku import SkuStatus  # noqa: E402
from app.services.purchase_target import default_sku_variant_display  # noqa: E402


class _Sku:
    def __init__(self, id, is_default=False, status=SkuStatus.ACTIVE, deleted_at=None):
        self.id = id
        self.is_default = is_default
        self.status = status
        self.deleted_at = deleted_at


class _PAttr:
    def __init__(self, sku_id, key, value, selectable=True):
        self.sku_id = sku_id
        self.attr_key_en = key
        self.attr_value_en = value
        self.selectable = selectable


class _Prod:
    def __init__(self, skus, attrs):
        self.skus = skus
        self.attrs = attrs


def test_default_display_multi_sku_picks_default():
    """多 SKU:落到 is_default(1L),展示与 cart 同口径,只拼值 '1L'。"""
    prod = _Prod(
        skus=[_Sku(id=1, is_default=True), _Sku(id=2)],
        attrs=[_PAttr(1, "spec", "1L"), _PAttr(2, "spec", "4L")],
    )
    assert default_sku_variant_display(prod) == "1L"


def test_default_display_simple_product_none():
    """简单商品:单默认 SKU 无 selectable 规格 → None(前端显示无具体规格)。"""
    prod = _Prod(skus=[_Sku(id=1, is_default=True)], attrs=[])
    assert default_sku_variant_display(prod) is None


def test_default_display_single_sku_without_default_flag():
    """仅 1 个 SKU、未标 is_default:仍视作默认(与 _decide_target 分支 2 一致)。"""
    prod = _Prod(skus=[_Sku(id=9)], attrs=[_PAttr(9, "size", "M")])
    assert default_sku_variant_display(prod) == "M"


def test_default_display_multi_sku_no_default_none():
    """多 SKU 且无 default(数据质量问题):无法预判 → None。"""
    prod = _Prod(
        skus=[_Sku(id=1), _Sku(id=2)],
        attrs=[_PAttr(1, "spec", "1L"), _PAttr(2, "spec", "4L")],
    )
    assert default_sku_variant_display(prod) is None


def test_default_display_excludes_non_selectable_attrs():
    """默认 SKU 上的非 selectable 属性不计入展示(与 _tuple_of 口径一致)。"""
    prod = _Prod(
        skus=[_Sku(id=1, is_default=True)],
        attrs=[_PAttr(1, "spec", "1L"), _PAttr(1, "note", "x", selectable=False)],
    )
    assert default_sku_variant_display(prod) == "1L"


def test_default_display_ignores_inactive_and_deleted_skus():
    """非 ACTIVE / 软删的 SKU 不参与默认挑选。"""
    prod = _Prod(
        skus=[
            _Sku(id=1, is_default=True, status=SkuStatus.INACTIVE),
            _Sku(id=2, deleted_at="2026-01-01"),
            _Sku(id=3, is_default=True),
        ],
        attrs=[_PAttr(3, "spec", "2L")],
    )
    assert default_sku_variant_display(prod) == "2L"


def test_default_display_no_skus_none():
    assert default_sku_variant_display(_Prod(skus=[], attrs=[])) is None

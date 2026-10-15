"""i18n_write 纯函数单测(不碰 DB)。"""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("src", ["zh", "en"])
def test_apply_i18n_prefilled_marks_src_and_manual(src):
    """预填值入口:三列全写,源 locale=src 其余 manual,不进翻译队列(i18n_pending_at 不动)。"""
    from app.core.i18n_write import apply_i18n_prefilled
    from app.db.models.product_attr import ProductAttr
    a = ProductAttr()
    apply_i18n_prefilled(a, "attr_key", {"zh": "规格", "en": "spec", "sw": "spec"}, src)
    assert (a.attr_key_zh, a.attr_key_en, a.attr_key_sw) == ("规格", "spec", "spec")
    assert a.trans_meta[f"attr_key_{src}"] == "src"
    assert all(a.trans_meta[f"attr_key_{loc}"] == "manual" for loc in ("zh", "en", "sw") if loc != src)
    assert a.i18n_pending_at is None


def test_apply_i18n_prefilled_rejects_missing_locale():
    from app.core.i18n_write import apply_i18n_prefilled
    from app.db.models.product_attr import ProductAttr
    with pytest.raises(ValueError):
        apply_i18n_prefilled(ProductAttr(), "attr_key", {"zh": "规格", "en": "spec"}, "zh")

"""i18n 基础设施测试 — 使用内存 dummy 模型,不依赖真实业务表和数据库。"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import BusinessError
from app.core.i18n import get_localized
from app.core.i18n_write import (
    _get_field_status,
    _get_meta,
    _set_meta,
    apply_i18n_create,
    apply_i18n_edit,
    retranslate_pending_or_failed,
)
from app.core.locale import DEFAULT_LOCALE, normalize_locale


# ---------------------------------------------------------------------------
# Dummy 模型:模拟有 I18nMixin 的业务表行
# ---------------------------------------------------------------------------

class DummyI18nRow:
    """模拟 I18nMixin + 分列字段的 ORM 行。"""

    def __init__(
        self,
        source_lang: str = "zh",
        name_zh: str | None = None,
        name_en: str | None = None,
    ):
        self.source_lang = source_lang
        self.name_zh = name_zh
        self.name_en = name_en
        self.trans_meta: dict = {}


class DummyLegacyRow:
    """模拟无 source_lang 的旧表行(如 categories)。"""

    def __init__(self, name_zh: str | None = None, name_en: str | None = None):
        self.name_zh = name_zh
        self.name_en = name_en


# ---------------------------------------------------------------------------
# normalize_locale
# ---------------------------------------------------------------------------

class TestNormalizeLocale:
    def test_none_returns_default(self):
        assert normalize_locale(None) == DEFAULT_LOCALE

    def test_empty_returns_default(self):
        assert normalize_locale("") == DEFAULT_LOCALE

    def test_zh_cn(self):
        assert normalize_locale("zh-CN") == "zh"

    def test_zh_tw(self):
        assert normalize_locale("zh-TW") == "zh"

    def test_zh_hant(self):
        assert normalize_locale("zh-Hant") == "zh"

    def test_en_us(self):
        assert normalize_locale("en-US") == "en"

    def test_en_gb(self):
        assert normalize_locale("en-GB") == "en"

    def test_bare_zh(self):
        assert normalize_locale("zh") == "zh"

    def test_bare_en(self):
        assert normalize_locale("en") == "en"

    def test_unsupported_falls_to_en(self):
        """不支持的语言兜底到 en(外国用户比中国用户更可能触发)。"""
        assert normalize_locale("fr") == "en"
        assert normalize_locale("ja-JP") == "en"

    def test_sw_supported(self):
        """sw 已接入,直接映射到 sw。"""
        assert normalize_locale("sw") == "sw"
        assert normalize_locale("sw-TZ") == "sw"
        assert normalize_locale("sw-KE") == "sw"

    def test_whitespace_stripped(self):
        assert normalize_locale("  en-US  ") == "en"

    def test_case_insensitive(self):
        assert normalize_locale("ZH-CN") == "zh"
        assert normalize_locale("EN-us") == "en"

    def test_unknown_subtag_with_known_base(self):
        """en-XX 这种未在映射表的子标签,base 命中 en。"""
        assert normalize_locale("en-XX") == "en"


# ---------------------------------------------------------------------------
# get_localized
# ---------------------------------------------------------------------------

class TestGetLocalized:
    def test_with_source_lang_fallback(self):
        """请求 locale=en 但 name_en 为空,回退到 source_lang=zh 列。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en=None)
        with patch("app.core.i18n.get_current_locale", return_value="en"):
            assert get_localized(row, "name") == "钢筋"

    def test_request_locale_hit(self):
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en="Rebar")
        with patch("app.core.i18n.get_current_locale", return_value="en"):
            assert get_localized(row, "name") == "Rebar"

    def test_legacy_row_no_source_lang(self):
        """无 source_lang 的旧表(categories)不报错,走 DEFAULT_LOCALE 兜底。"""
        row = DummyLegacyRow(name_zh="水泥", name_en=None)
        with patch("app.core.i18n.get_current_locale", return_value="en"):
            assert get_localized(row, "name") == "水泥"

    def test_legacy_row_request_locale_hit(self):
        row = DummyLegacyRow(name_zh="水泥", name_en="Cement")
        with patch("app.core.i18n.get_current_locale", return_value="en"):
            assert get_localized(row, "name") == "Cement"

    def test_all_empty_returns_empty_string(self):
        row = DummyI18nRow(source_lang="zh", name_zh=None, name_en=None)
        with patch("app.core.i18n.get_current_locale", return_value="en"):
            assert get_localized(row, "name") == ""

    def test_source_lang_en_fallback_to_en(self):
        """source_lang=en, 请求 zh, name_zh 为空 → 回退 name_en。"""
        row = DummyI18nRow(source_lang="en", name_zh=None, name_en="Rebar")
        with patch("app.core.i18n.get_current_locale", return_value="zh"):
            assert get_localized(row, "name") == "Rebar"


# ---------------------------------------------------------------------------
# trans_meta 工具函数
# ---------------------------------------------------------------------------

class TestMetaHelpers:
    def test_get_meta_empty(self):
        row = DummyI18nRow()
        assert _get_meta(row) == {}

    def test_set_meta(self):
        row = DummyI18nRow()
        _set_meta(row, {"name_zh": "src"})
        assert row.trans_meta == {"name_zh": "src"}

    def test_get_meta_returns_copy(self):
        """修改返回值不影响原对象。"""
        row = DummyI18nRow()
        row.trans_meta = {"name_zh": "src"}
        meta = _get_meta(row)
        meta["name_en"] = "auto"
        assert "name_en" not in row.trans_meta

    def test_get_field_status(self):
        row = DummyI18nRow()
        row.trans_meta = {"name_zh": "src", "name_en": "auto"}
        assert _get_field_status(row, "name", "zh") == "src"
        assert _get_field_status(row, "name", "en") == "auto"
        assert _get_field_status(row, "desc", "zh") is None


# ---------------------------------------------------------------------------
# apply_i18n_create
# ---------------------------------------------------------------------------

class TestApplyI18nCreate:
    @pytest.mark.asyncio
    async def test_create_sets_source_and_auto(self):
        row = DummyI18nRow(source_lang="zh")
        await apply_i18n_create(row, "name", "钢筋", "zh")

        assert row.name_zh == "钢筋"
        assert row.name_en == "钢筋"  # mock 翻译返回原文
        assert row.trans_meta["name_zh"] == "src"
        assert row.trans_meta["name_en"] == "auto"

    @pytest.mark.asyncio
    async def test_create_source_en(self):
        row = DummyI18nRow(source_lang="en")
        await apply_i18n_create(row, "name", "Rebar", "en")

        assert row.name_en == "Rebar"
        assert row.name_zh == "Rebar"  # mock
        assert row.trans_meta["name_en"] == "src"
        assert row.trans_meta["name_zh"] == "auto"

    @pytest.mark.asyncio
    async def test_create_translation_failure_marks_failed(self):
        row = DummyI18nRow(source_lang="zh")
        with patch(
            "app.core.i18n_write.translate_text",
            side_effect=RuntimeError("API down"),
        ):
            await apply_i18n_create(row, "name", "钢筋", "zh")

        assert row.name_zh == "钢筋"
        assert row.trans_meta["name_zh"] == "src"
        assert row.trans_meta["name_en"] == "failed"


# ---------------------------------------------------------------------------
# apply_i18n_edit
# ---------------------------------------------------------------------------

class TestApplyI18nEdit:
    @pytest.mark.asyncio
    async def test_edit_source_retranslates_auto(self):
        """编辑源语言 → auto 列被重新翻译。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en="Rebar")
        row.trans_meta = {"name_zh": "src", "name_en": "auto"}

        await apply_i18n_edit(row, "name", "zh", "螺纹钢", "钢筋")

        assert row.name_zh == "螺纹钢"
        assert row.name_en == "螺纹钢"  # mock 返回原文
        assert row.trans_meta["name_zh"] == "src"
        assert row.trans_meta["name_en"] == "auto"

    @pytest.mark.asyncio
    async def test_edit_source_stales_manual(self):
        """编辑源语言 → manual 列标 stale,值不覆盖。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en="Steel Bar")
        row.trans_meta = {"name_zh": "src", "name_en": "manual"}

        await apply_i18n_edit(row, "name", "zh", "螺纹钢", "钢筋")

        assert row.name_zh == "螺纹钢"
        assert row.name_en == "Steel Bar"  # 值保留
        assert row.trans_meta["name_en"] == "stale"

    @pytest.mark.asyncio
    async def test_edit_translation_marks_manual(self):
        """编辑非源语言 → 标 manual,其他列不动。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en="Rebar")
        row.trans_meta = {"name_zh": "src", "name_en": "auto"}

        await apply_i18n_edit(row, "name", "en", "Steel Bar", "Rebar")

        assert row.name_en == "Steel Bar"
        assert row.trans_meta["name_en"] == "manual"
        assert row.trans_meta["name_zh"] == "src"  # 不变

    @pytest.mark.asyncio
    async def test_diff_principle_no_change(self):
        """值未变时不更新 trans_meta。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en="Rebar")
        row.trans_meta = {"name_zh": "src", "name_en": "auto"}

        await apply_i18n_edit(row, "name", "zh", "钢筋", "钢筋")

        # trans_meta 不变
        assert row.trans_meta["name_en"] == "auto"

    @pytest.mark.asyncio
    async def test_edit_source_translate_failure(self):
        """编辑源语言时翻译失败 → 标 failed,不阻塞。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en="Rebar")
        row.trans_meta = {"name_zh": "src", "name_en": "auto"}

        with patch(
            "app.core.i18n_write.translate_text",
            side_effect=RuntimeError("timeout"),
        ):
            await apply_i18n_edit(row, "name", "zh", "螺纹钢", "钢筋")

        assert row.name_zh == "螺纹钢"
        assert row.trans_meta["name_en"] == "failed"


# ---------------------------------------------------------------------------
# retranslate_pending_or_failed
# ---------------------------------------------------------------------------

class TestRetranslatePendingOrFailed:
    @pytest.mark.asyncio
    async def test_retranslate_failed(self):
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en=None)
        row.trans_meta = {"name_zh": "src", "name_en": "failed"}

        await retranslate_pending_or_failed(row, "name")

        assert row.name_en == "钢筋"  # mock
        assert row.trans_meta["name_en"] == "auto"

    @pytest.mark.asyncio
    async def test_retranslate_pending(self):
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en=None)
        row.trans_meta = {"name_zh": "src", "name_en": "pending"}

        await retranslate_pending_or_failed(row, "name")

        assert row.trans_meta["name_en"] == "auto"

    @pytest.mark.asyncio
    async def test_retranslate_skips_non_pending(self):
        """manual / auto / src / stale 不重试。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en="Steel Bar")
        row.trans_meta = {"name_zh": "src", "name_en": "manual"}

        await retranslate_pending_or_failed(row, "name")

        assert row.name_en == "Steel Bar"
        assert row.trans_meta["name_en"] == "manual"

    @pytest.mark.asyncio
    async def test_retranslate_no_source_lang(self):
        """无 source_lang 的对象静默跳过。"""
        row = DummyLegacyRow(name_zh="水泥", name_en=None)
        await retranslate_pending_or_failed(row, "name")  # 不报错

    @pytest.mark.asyncio
    async def test_retranslate_still_fails(self):
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en=None)
        row.trans_meta = {"name_zh": "src", "name_en": "failed"}

        with patch(
            "app.core.i18n_write.translate_text",
            side_effect=RuntimeError("still down"),
        ):
            await retranslate_pending_or_failed(row, "name")

        assert row.trans_meta["name_en"] == "failed"


# ---------------------------------------------------------------------------
# BusinessError message_params
# ---------------------------------------------------------------------------

class TestBusinessErrorMessageParams:
    def test_message_params_default_none(self):
        err = BusinessError(400, 40001, "test")
        assert err.message_params is None

    def test_message_params_set(self):
        err = BusinessError(400, 40001, "test", message_params={"field": "email"})
        assert err.message_params == {"field": "email"}

    def test_subclass_inherits_message_params(self):
        """子类通过 **kwargs 或直接传递也能设置 message_params。"""
        from app.core.exceptions import NotFoundError
        err = NotFoundError("Item not found")
        # 子类未显式传 message_params,应为 None
        assert err.message_params is None

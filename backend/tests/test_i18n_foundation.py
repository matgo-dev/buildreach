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
    process_pending_translations,
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
        self.i18n_pending_at = None


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

    def test_sw_fallback_to_en_before_zh(self):
        """请求 sw, name_sw 为空, name_en 有值 → 回退 en 而非 zh。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en="Rebar")
        row.name_sw = None
        with patch("app.core.i18n.get_current_locale", return_value="sw"):
            assert get_localized(row, "name") == "Rebar"

    def test_sw_fallback_to_zh_when_en_also_empty(self):
        """请求 sw, name_sw 和 name_en 都空 → 最终回退 source_lang(zh)。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en=None)
        row.name_sw = None
        with patch("app.core.i18n.get_current_locale", return_value="sw"):
            assert get_localized(row, "name") == "钢筋"

    def test_sw_direct_hit(self):
        """请求 sw, name_sw 有值 → 直接返回。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en="Rebar")
        row.name_sw = "Chuma"
        with patch("app.core.i18n.get_current_locale", return_value="sw"):
            assert get_localized(row, "name") == "Chuma"


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
# apply_i18n_create(异步化:只标 pending,不内联翻译)
# ---------------------------------------------------------------------------

class TestApplyI18nCreate:
    @pytest.mark.asyncio
    async def test_create_sets_source_and_pending(self):
        """创建时源列写值标 src,其他 locale 标 pending。"""
        row = DummyI18nRow(source_lang="zh")
        await apply_i18n_create(row, "name", "钢筋", "zh")

        assert row.name_zh == "钢筋"
        assert row.trans_meta["name_zh"] == "src"
        assert row.trans_meta["name_en"] == "pending"
        assert row.trans_meta.get("name_sw") == "pending"
        assert row.i18n_pending_at is not None

    @pytest.mark.asyncio
    async def test_create_source_en(self):
        row = DummyI18nRow(source_lang="en")
        await apply_i18n_create(row, "name", "Rebar", "en")

        assert row.name_en == "Rebar"
        assert row.trans_meta["name_en"] == "src"
        assert row.trans_meta["name_zh"] == "pending"


# ---------------------------------------------------------------------------
# apply_i18n_edit(异步化:只标 pending/stale,不内联翻译)
# ---------------------------------------------------------------------------

class TestApplyI18nEdit:
    @pytest.mark.asyncio
    async def test_edit_source_marks_pending(self):
        """编辑源语言 → auto 列标 pending。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en="Rebar")
        row.trans_meta = {"name_zh": "src", "name_en": "auto"}

        await apply_i18n_edit(row, "name", "zh", "螺纹钢", "钢筋")

        assert row.name_zh == "螺纹钢"
        assert row.trans_meta["name_zh"] == "src"
        assert row.trans_meta["name_en"] == "pending"

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


# ---------------------------------------------------------------------------
# process_pending_translations(后台任务调翻译 API)
# ---------------------------------------------------------------------------

class TestProcessPendingTranslations:
    @pytest.mark.asyncio
    async def test_process_pending_translates(self):
        """pending 状态被翻译 → auto。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en=None)
        row.trans_meta = {"name_zh": "src", "name_en": "pending"}

        await process_pending_translations(row)

        # mock provider 返回源文
        assert row.name_en == "钢筋"
        assert row.trans_meta["name_en"] == "mock"
        assert row.i18n_pending_at is None  # 无剩余 pending

    @pytest.mark.asyncio
    async def test_process_failed_retries(self):
        """failed 状态也会被重试。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en=None)
        row.trans_meta = {"name_zh": "src", "name_en": "failed"}

        await process_pending_translations(row)

        assert row.name_en == "钢筋"
        assert row.trans_meta["name_en"] == "mock"

    @pytest.mark.asyncio
    async def test_process_skips_manual(self):
        """manual/auto/src/stale 不处理。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en="Steel Bar")
        row.trans_meta = {"name_zh": "src", "name_en": "manual"}

        await process_pending_translations(row)

        assert row.name_en == "Steel Bar"
        assert row.trans_meta["name_en"] == "manual"

    @pytest.mark.asyncio
    async def test_process_translate_failure_marks_failed(self):
        """翻译抛异常 → 标 failed。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en=None)
        row.trans_meta = {"name_zh": "src", "name_en": "pending"}

        with patch(
            "app.core.i18n_write.translate_text",
            side_effect=RuntimeError("API down"),
        ):
            await process_pending_translations(row)

        assert row.trans_meta["name_en"] == "failed"

    @pytest.mark.asyncio
    async def test_process_skipped_keeps_pending(self):
        """provider=none 时 status=skipped,保持 pending 不改。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en=None)
        row.trans_meta = {"name_zh": "src", "name_en": "pending"}

        with patch(
            "app.core.i18n_write.translate_text",
            return_value={"translated": "钢筋", "status": "skipped"},
        ):
            await process_pending_translations(row)

        assert row.trans_meta["name_en"] == "pending"


# ---------------------------------------------------------------------------
# retranslate_pending_or_failed(兼容旧接口)
# ---------------------------------------------------------------------------

class TestRetranslatePendingOrFailed:
    @pytest.mark.asyncio
    async def test_retranslate_delegates(self):
        """retranslate_pending_or_failed 委托给 process_pending_translations。"""
        row = DummyI18nRow(source_lang="zh", name_zh="钢筋", name_en=None)
        row.trans_meta = {"name_zh": "src", "name_en": "pending"}

        await retranslate_pending_or_failed(row, "name")

        assert row.name_en == "钢筋"
        assert row.trans_meta["name_en"] == "mock"

    @pytest.mark.asyncio
    async def test_retranslate_no_source_lang(self):
        """无 source_lang 的对象静默跳过。"""
        row = DummyLegacyRow(name_zh="水泥", name_en=None)
        await retranslate_pending_or_failed(row, "name")  # 不报错


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

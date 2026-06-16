"""normalize_phone_to_e164 单测 — TZ/CN happy + edge cases。"""
import pytest

from app.core.exceptions import PhoneFormatError, PhoneUnsupportedRegionError
from app.core.phone import normalize_phone_to_e164


# ── TZ happy path ──────────────────────────────────────────────

class TestTzHappy:
    def test_tz_e164_passthrough(self):
        assert normalize_phone_to_e164("+255712345678", "TZ") == "+255712345678"

    def test_tz_local_leading_zero(self):
        """0712345678 → +255712345678"""
        assert normalize_phone_to_e164("0712345678", "TZ") == "+255712345678"

    def test_tz_no_prefix(self):
        """712345678 → +255712345678"""
        assert normalize_phone_to_e164("712345678", "TZ") == "+255712345678"

    def test_tz_with_spaces(self):
        assert normalize_phone_to_e164("+255 712 345 678", "TZ") == "+255712345678"

    def test_tz_with_dashes(self):
        assert normalize_phone_to_e164("+255-712-345-678", "TZ") == "+255712345678"

    def test_tz_e164_ignores_region(self):
        """raw 已带 +255 时 region 参数不影响结果。"""
        assert normalize_phone_to_e164("+255712345678", "CN") == "+255712345678"
        assert normalize_phone_to_e164("+255712345678", None) == "+255712345678"


# ── CN happy path ──────────────────────────────────────────────

class TestCnHappy:
    def test_cn_e164_passthrough(self):
        assert normalize_phone_to_e164("+8613800138000", "CN") == "+8613800138000"

    def test_cn_bare_11_digits(self):
        """13800138000 + region=CN → +8613800138000"""
        assert normalize_phone_to_e164("13800138000", "CN") == "+8613800138000"

    def test_cn_with_spaces(self):
        assert normalize_phone_to_e164("138 0013 8000", "CN") == "+8613800138000"

    def test_cn_e164_ignores_region(self):
        """raw 带 +86 时 region 参数无所谓。"""
        assert normalize_phone_to_e164("+8613800138000", "TZ") == "+8613800138000"
        assert normalize_phone_to_e164("+8613800138000", None) == "+8613800138000"


# ── 同号多格式一致性 ──────────────────────────────────────────

class TestConsistency:
    def test_tz_variants_same_result(self):
        variants = ["0712345678", "712345678", "+255712345678", " +255 712 345 678 "]
        results = {normalize_phone_to_e164(v, "TZ") for v in variants}
        assert len(results) == 1
        assert results.pop() == "+255712345678"

    def test_cn_variants_same_result(self):
        variants = ["13800138000", "+8613800138000", " +86 138 0013 8000 "]
        results = {normalize_phone_to_e164(v, "CN") for v in variants}
        assert len(results) == 1
        assert results.pop() == "+8613800138000"


# ── 非法号码 → PhoneFormatError ────────────────────────────────

class TestFormatError:
    def test_empty_string(self):
        with pytest.raises(PhoneFormatError):
            normalize_phone_to_e164("", "TZ")

    def test_pure_whitespace(self):
        with pytest.raises(PhoneFormatError):
            normalize_phone_to_e164("   ", "TZ")

    def test_too_short(self):
        with pytest.raises(PhoneFormatError):
            normalize_phone_to_e164("123", "TZ")

    def test_letters(self):
        with pytest.raises(PhoneFormatError):
            normalize_phone_to_e164("abcdef", "TZ")

    def test_tz_invalid_segment(self):
        """坦桑号段不合法(如 +255112345678 不存在的号段)。"""
        with pytest.raises(PhoneFormatError):
            normalize_phone_to_e164("+255112345678", "TZ")

    def test_cn_invalid_segment(self):
        """中国号段不合法(如 10000000000)。"""
        with pytest.raises(PhoneFormatError):
            normalize_phone_to_e164("10000000000", "CN")


# ── 不支持的国家 → PhoneUnsupportedRegionError ─────────────────

class TestUnsupportedRegion:
    def test_kenya_number(self):
        """+254 (肯尼亚) 不在 SUPPORTED_REGIONS。"""
        with pytest.raises(PhoneUnsupportedRegionError):
            normalize_phone_to_e164("+254712345678", "TZ")

    def test_us_number(self):
        with pytest.raises(PhoneUnsupportedRegionError):
            normalize_phone_to_e164("+12025551234", None)

    def test_region_param_unsupported(self):
        """region='KE' 不受支持,但关键是号码解析后的实际归属。"""
        with pytest.raises(PhoneUnsupportedRegionError):
            normalize_phone_to_e164("0712345678", "KE")

"""邮箱验证相关纯逻辑的单元测试(不依赖 HTTP / DB)。

覆盖:
- Settings.smtp_configured 计算属性
- config.email_verification_misconfigured 启动 fail-fast 判定
- services.contact.build_contact_payload 联系方式 payload 构建
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.core.config import email_verification_misconfigured, settings
from app.services.contact import build_contact_payload


# ---- Settings.smtp_configured ----

class TestSmtpConfigured:
    def test_all_present(self, monkeypatch):
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
        monkeypatch.setattr(settings, "SMTP_USER", "user")
        monkeypatch.setattr(settings, "SMTP_PASSWORD", "pass")
        assert settings.smtp_configured is True

    def test_missing_host(self, monkeypatch):
        monkeypatch.setattr(settings, "SMTP_HOST", "")
        monkeypatch.setattr(settings, "SMTP_USER", "user")
        monkeypatch.setattr(settings, "SMTP_PASSWORD", "pass")
        assert settings.smtp_configured is False

    def test_missing_password(self, monkeypatch):
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
        monkeypatch.setattr(settings, "SMTP_USER", "user")
        monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
        assert settings.smtp_configured is False

    def test_all_empty(self, monkeypatch):
        monkeypatch.setattr(settings, "SMTP_HOST", "")
        monkeypatch.setattr(settings, "SMTP_USER", "")
        monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
        assert settings.smtp_configured is False


# ---- email_verification_misconfigured(fail-fast 判定) ----

def _fake(*, require: bool, smtp: bool, dev_log: bool) -> SimpleNamespace:
    return SimpleNamespace(
        REQUIRE_EMAIL_VERIFICATION=require,
        smtp_configured=smtp,
        EMAIL_DEV_LOG_CODES=dev_log,
    )


class TestEmailVerificationMisconfigured:
    def test_on_without_smtp_or_devlog_is_misconfigured(self):
        # 唯一应 fail-fast 的组合:要求验证 + 无 SMTP + 未开 DEV 日志
        assert email_verification_misconfigured(_fake(require=True, smtp=False, dev_log=False)) is True

    def test_on_with_smtp_ok(self):
        assert email_verification_misconfigured(_fake(require=True, smtp=True, dev_log=False)) is False

    def test_on_with_devlog_ok(self):
        # SMTP 未配置但开了 DEV 日志(本地/CI 场景)→ 允许启动
        assert email_verification_misconfigured(_fake(require=True, smtp=False, dev_log=True)) is False

    def test_off_never_misconfigured(self):
        # 关闭验证时,SMTP 状态无关紧要
        assert email_verification_misconfigured(_fake(require=False, smtp=False, dev_log=False)) is False
        assert email_verification_misconfigured(_fake(require=False, smtp=True, dev_log=False)) is False


# ---- build_contact_payload ----

class TestBuildContactPayload:
    def test_all_configured(self):
        with patch("app.services.contact.settings") as mock_s:
            mock_s.WHATSAPP_DEFAULT_NUMBER = "+255 697 123 456"
            mock_s.CONTACT_EMAIL = "support@example.com"
            mock_s.WECHAT_ID = "Matgo_Service"
            mock_s.WECHAT_QR_IMAGE = "/contact/wechat-qr.png"
            assert build_contact_payload() == {
                "whatsapp_link": "https://wa.me/255697123456",
                "whatsapp_number": "+255 697 123 456",
                "wechat_id": "Matgo_Service",
                "wechat_qr_image": "/contact/wechat-qr.png",
                "email": "support@example.com",
            }

    def test_blank_fields_become_null(self):
        with patch("app.services.contact.settings") as mock_s:
            mock_s.WHATSAPP_DEFAULT_NUMBER = ""
            mock_s.CONTACT_EMAIL = ""
            mock_s.WECHAT_ID = "   "     # 纯空白视为未配置
            mock_s.WECHAT_QR_IMAGE = ""
            payload = build_contact_payload()
        assert payload["whatsapp_link"] is None
        assert payload["whatsapp_number"] is None
        assert payload["wechat_id"] is None
        assert payload["wechat_qr_image"] is None
        assert payload["email"] is None

    def test_number_present_but_unparseable_nulls_number(self):
        # 号码只有符号 → 解析不出链接,number 也应为 None(与 link 一致)
        with patch("app.services.contact.settings") as mock_s:
            mock_s.WHATSAPP_DEFAULT_NUMBER = "+  - "
            mock_s.CONTACT_EMAIL = "a@b.com"
            mock_s.WECHAT_ID = ""
            mock_s.WECHAT_QR_IMAGE = ""
            payload = build_contact_payload()
        assert payload["whatsapp_link"] is None
        assert payload["whatsapp_number"] is None
        assert payload["email"] == "a@b.com"

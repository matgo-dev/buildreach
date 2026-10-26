"""系统告警纯逻辑单测(不碰 DB/HTTP):故障判定、状态迁移、邮件日限流、横幅快照。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import parse_email_list
from app.services import email_service
from app.services.system_alerts import (
    TranslationHealth,
    apply_sweep_result,
    build_alert_items,
    is_provider_down,
    should_send_alert,
)

T0 = datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)


class TestIsProviderDown:
    def test_all_failed_is_down(self):
        assert is_provider_down({"scanned": 100, "translated": 0, "failed": 100}) is True

    def test_partial_failure_is_row_problem_not_down(self):
        assert is_provider_down({"scanned": 100, "translated": 97, "failed": 3}) is False

    def test_nothing_pending_is_healthy(self):
        assert is_provider_down({"scanned": 0, "translated": 0, "failed": 0}) is False


class TestApplySweepResult:
    def test_down_then_still_down_then_recovered(self):
        s = TranslationHealth()
        assert apply_sweep_result(s, {"translated": 0, "failed": 100}, "403 userRateLimitExceeded", T0) == "down_started"
        assert s.down_since == T0
        assert s.last_error == "403 userRateLimitExceeded"

        t1 = T0 + timedelta(minutes=5)
        assert apply_sweep_result(s, {"translated": 0, "failed": 100}, None, t1) == "still_down"
        assert s.down_since == T0  # 故障开始时间不被后续轮次覆盖
        assert s.last_error == "403 userRateLimitExceeded"  # 本轮没新错误原文则保留上次

        t2 = T0 + timedelta(minutes=10)
        assert apply_sweep_result(s, {"translated": 100, "failed": 0}, None, t2) == "recovered"
        assert s.down_since is None
        assert s.last_error is None
        assert s.last_alert_sent_at is None

    def test_ok_stays_ok(self):
        s = TranslationHealth()
        assert apply_sweep_result(s, {"translated": 5, "failed": 0}, None, T0) == "ok"
        assert apply_sweep_result(s, {"translated": 0, "failed": 0}, None, T0) == "ok"
        assert s.is_down is False

    def test_empty_sweep_clears_down(self):
        """待译行被清空(例如人工处理)后不该一直挂着告警。"""
        s = TranslationHealth(down_since=T0)
        assert apply_sweep_result(s, {"translated": 0, "failed": 0}, None, T0 + timedelta(hours=1)) == "recovered"


class TestShouldSendAlert:
    def test_first_down_sends(self):
        s = TranslationHealth(down_since=T0)
        assert should_send_alert(s, "down_started", T0) is True

    def test_same_outage_once_per_day(self):
        s = TranslationHealth(down_since=T0, last_alert_sent_at=T0)
        assert should_send_alert(s, "still_down", T0 + timedelta(hours=23)) is False
        assert should_send_alert(s, "still_down", T0 + timedelta(hours=24)) is True

    def test_recovered_always_sends(self):
        s = TranslationHealth(last_alert_sent_at=T0)
        assert should_send_alert(s, "recovered", T0 + timedelta(minutes=5)) is True

    def test_ok_never_sends(self):
        assert should_send_alert(TranslationHealth(), "ok", T0) is False


class TestBuildAlertItems:
    def test_empty_when_healthy(self):
        assert build_alert_items(TranslationHealth(), None) == []

    def test_item_when_down(self):
        s = TranslationHealth(down_since=T0, last_error="403 userRateLimitExceeded", last_failed_rows=100)
        items = build_alert_items(s, 47)
        assert items == [{
            "kind": "translation_down",
            "since": T0.isoformat(),
            "detail": "403 userRateLimitExceeded",
            "pending_rows": 47,
        }]

    def test_pending_rows_falls_back_to_last_failed(self):
        s = TranslationHealth(down_since=T0, last_failed_rows=100)
        assert build_alert_items(s, None)[0]["pending_rows"] == 100


class TestDescribeProviderError:
    """告警里的错误原文不能带凭据(Google key 在请求 URL 的 query 里)。"""

    def test_http_error_keeps_status_and_body_not_url(self):
        import httpx
        from app.services.translation_service import describe_provider_error

        req = httpx.Request("POST", "https://translation.googleapis.com/language/translate/v2?key=AIzaSECRET")
        resp = httpx.Response(403, request=req, text='{"error": {"message": "userRateLimitExceeded"}}')
        err = httpx.HTTPStatusError("boom", request=req, response=resp)
        out = describe_provider_error(err)
        assert out.startswith("HTTP 403")
        assert "userRateLimitExceeded" in out
        assert "AIzaSECRET" not in out

    def test_plain_exception_redacts_credential_params(self):
        from app.services.translation_service import describe_provider_error

        out = describe_provider_error(RuntimeError("GET https://x/y?key=AIza123&secret=abc failed"))
        assert "AIza123" not in out and "abc" not in out
        assert "key=***" in out and "secret=***" in out
        assert out.startswith("RuntimeError:")


class TestParseEmailList:
    def test_single(self):
        assert parse_email_list("a@x.com") == ["a@x.com"]

    def test_comma_semicolon_and_spaces(self):
        assert parse_email_list(" a@x.com , b@y.com;c@z.com ") == ["a@x.com", "b@y.com", "c@z.com"]

    def test_dedupe_case_insensitive_keeps_order(self):
        assert parse_email_list("A@x.com,b@y.com,a@X.com") == ["A@x.com", "b@y.com"]

    def test_empty_and_only_separators(self):
        assert parse_email_list("") == []
        assert parse_email_list(" , ; ") == []


class TestSendSystemAlertEmail:
    def _configure(self, monkeypatch, alert_email: str):
        monkeypatch.setattr(email_service.settings, "ALERT_EMAIL", alert_email)
        monkeypatch.setattr(email_service.settings, "SMTP_HOST", "smtp.example.com")
        monkeypatch.setattr(email_service.settings, "SMTP_USER", "u")
        monkeypatch.setattr(email_service.settings, "SMTP_PASSWORD", "p")
        monkeypatch.setattr(email_service.settings, "SMTP_FROM_EMAIL", "no-reply@example.com")

    def test_sends_one_mail_to_all_recipients(self, monkeypatch):
        self._configure(monkeypatch, "a@x.com, b@y.com")
        calls: list[tuple] = []
        monkeypatch.setattr(email_service, "_smtp_send", lambda to, payload: calls.append((to, payload)))
        assert email_service.send_system_alert_email("subj", "body") is True
        assert len(calls) == 1
        to, payload = calls[0]
        assert to == ["a@x.com", "b@y.com"]
        assert "To: a@x.com, b@y.com" in payload

    def test_no_recipients_means_no_send(self, monkeypatch):
        self._configure(monkeypatch, " ; ")
        monkeypatch.setattr(email_service, "_smtp_send", lambda to, payload: (_ for _ in ()).throw(AssertionError("must not send")))
        assert email_service.send_system_alert_email("subj", "body") is False

    def test_smtp_failure_returns_false(self, monkeypatch):
        self._configure(monkeypatch, "a@x.com")
        def boom(to, payload):
            raise RuntimeError("smtp down")
        monkeypatch.setattr(email_service, "_smtp_send", boom)
        assert email_service.send_system_alert_email("subj", "body") is False

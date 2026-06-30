from __future__ import annotations

from starlette.requests import Request

from app.core.config import settings
from app.core.request_ip import get_client_ip


def _request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers or [],
        "client": ("127.0.0.1", 12345),
    })


def test_get_client_ip_ignores_proxy_headers_by_default(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY", False)
    req = _request([(b"x-forwarded-for", b"1.2.3.4")])

    assert get_client_ip(req) == "127.0.0.1"


def test_get_client_ip_uses_trusted_proxy_headers(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY", True)
    req = _request([
        (b"x-forwarded-for", b"1.2.3.4, 10.0.0.1"),
        (b"x-real-ip", b"5.6.7.8"),
    ])

    assert get_client_ip(req) == "5.6.7.8"


def test_get_client_ip_falls_back_to_x_forwarded_for(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY", True)
    req = _request([(b"x-forwarded-for", b"1.2.3.4, 10.0.0.1")])

    assert get_client_ip(req) == "1.2.3.4"

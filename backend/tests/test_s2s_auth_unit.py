"""前台互通纯逻辑单测:S2S 令牌签验口径、组织解析判定、配置自洽判定。不碰 DB/HTTP。"""
from __future__ import annotations

import time

import pytest
from jose import jwt

from app.core import s2s_auth
from app.core.config import Settings, s2s_misconfigured, settings
from app.core.s2s_auth import (
    AUD_FULFILLMENT_PORTAL,
    AUD_MATGO_INTERNAL,
    ISS_FULFILLMENT,
    ISS_MATGO,
    S2SError,
    sign_s2s_token,
    verify_s2s_token,
)
from app.services.buyer_org_binding import classify_memberships

SECRET = settings.S2S_SHARED_SECRET
assert len(SECRET) >= 32, "conftest 必须注入测试密钥"


def _claims(**override) -> dict:
    now = int(time.time())
    base = {
        "iss": ISS_FULFILLMENT, "aud": AUD_MATGO_INTERNAL, "sub": "svc:fulfillment",
        "typ": "s2s", "iat": now, "exp": now + 60, "jti": "abc123",
    }
    base.update(override)
    return {k: v for k, v in base.items() if v is not None}


def _encode(claims: dict, secret: str = SECRET) -> str:
    return jwt.encode(claims, secret, algorithm="HS256")


def _verify_internal(token: str, now: int | None = None):
    return verify_s2s_token(token, issuer=ISS_FULFILLMENT, audience=AUD_MATGO_INTERNAL, now=now)


# ── 签发 ──────────────────────────────────────────────────

def test_sign_then_verify_roundtrip():
    token, jti = sign_s2s_token(iss=ISS_FULFILLMENT, aud=AUD_MATGO_INTERNAL, sub="svc:fulfillment")
    p = _verify_internal(token)
    assert (p.iss, p.sub, p.jti) == (ISS_FULFILLMENT, "svc:fulfillment", jti)


def test_sign_ttl_is_exactly_60s_and_jti_unique():
    t1, j1 = sign_s2s_token(iss=ISS_MATGO, aud=AUD_FULFILLMENT_PORTAL, sub="org:7", now=1_000_000)
    t2, j2 = sign_s2s_token(iss=ISS_MATGO, aud=AUD_FULFILLMENT_PORTAL, sub="org:7", now=1_000_000)
    c = jwt.get_unverified_claims(t1)
    assert c["exp"] - c["iat"] == s2s_auth.S2S_TTL_SECONDS
    assert c["typ"] == "s2s" and c["sub"] == "org:7"
    assert j1 != j2


def test_sign_without_secret_refuses(monkeypatch):
    monkeypatch.setattr(settings, "S2S_SHARED_SECRET", "")
    with pytest.raises(S2SError):
        sign_s2s_token(iss=ISS_MATGO, aud=AUD_FULFILLMENT_PORTAL, sub="org:1")


# ── 校验:契约 §3 七项各错一次 ─────────────────────────────

def test_verify_wrong_secret():
    with pytest.raises(S2SError):
        _verify_internal(_encode(_claims(), secret="x" * 40))


def test_verify_wrong_algorithm_rejected():
    token = jwt.encode(_claims(), SECRET, algorithm="HS512")
    with pytest.raises(S2SError):
        _verify_internal(token)


def test_verify_reverse_replay_by_aud():
    """matgo→履约的令牌(aud=fulfillment-portal)打 matgo 内部端点,由 aud 拒。"""
    token, _ = sign_s2s_token(iss=ISS_MATGO, aud=AUD_FULFILLMENT_PORTAL, sub="org:1")
    with pytest.raises(S2SError):
        _verify_internal(token)


def test_verify_wrong_iss():
    with pytest.raises(S2SError):
        _verify_internal(_encode(_claims(iss=ISS_MATGO)))


@pytest.mark.parametrize("missing", ["iss", "aud", "sub", "jti", "exp", "iat"])
def test_verify_missing_required_claim(missing):
    with pytest.raises(S2SError):
        _verify_internal(_encode(_claims(**{missing: None})))


@pytest.mark.parametrize("typ", [None, "access", "S2S"])
def test_verify_wrong_typ(typ):
    with pytest.raises(S2SError):
        _verify_internal(_encode(_claims(typ=typ)))


def test_verify_long_ttl_rejected():
    """exp−iat=3600:绝对 exp 仍在未来,但超出所称 60s 窗 → 拒。"""
    now = int(time.time())
    with pytest.raises(S2SError):
        _verify_internal(_encode(_claims(iat=now, exp=now + 3600)))


def test_verify_ttl_at_boundary_accepted():
    now = int(time.time())
    assert _verify_internal(_encode(_claims(iat=now, exp=now + 60)), now=now)


def test_verify_zero_or_negative_ttl_rejected():
    now = int(time.time())
    with pytest.raises(S2SError):
        _verify_internal(_encode(_claims(iat=now, exp=now)), now=now)


def test_verify_future_iat_rejected():
    """iat=now+120 且 exp=iat+60:签名方时钟或伪造,超出 30s 偏差 → 拒。"""
    now = int(time.time())
    with pytest.raises(S2SError):
        _verify_internal(_encode(_claims(iat=now + 120, exp=now + 180)), now=now)


def test_verify_small_clock_skew_tolerated():
    now = int(time.time())
    assert _verify_internal(_encode(_claims(iat=now + 20, exp=now + 80)), now=now)


def test_verify_expired_beyond_leeway_rejected():
    now = int(time.time())
    with pytest.raises(S2SError):
        _verify_internal(_encode(_claims(iat=now - 200, exp=now - 140)))


def test_verify_exp_uses_the_same_clock_as_iat():
    """exp 也按传入的 now 校(一个函数一个时钟):墙钟看仍有效的令牌,按未来 now 判已过期。"""
    now = int(time.time())
    token = _encode(_claims(iat=now, exp=now + 60))
    assert _verify_internal(token, now=now + 89)          # exp + 30s 容差内
    with pytest.raises(S2SError):
        _verify_internal(token, now=now + 91)             # 超出容差


def test_verify_without_secret_refuses(monkeypatch):
    token = _encode(_claims())
    monkeypatch.setattr(settings, "S2S_SHARED_SECRET", "")
    with pytest.raises(S2SError):
        _verify_internal(token)


def test_verify_empty_sub_or_jti_rejected():
    with pytest.raises(S2SError):
        _verify_internal(_encode(_claims(jti="")))


# ── 组织解析判定(契约 §5.2 BLOCKER B3)─────────────────────

@pytest.mark.parametrize("count, first, status, org_id, state", [
    (0, None, None, None, "NO_ORG"),
    (1, 5, "ACTIVE", 5, None),
    (1, 5, "DISABLED", None, "ORG_DISABLED"),
    (2, 5, "ACTIVE", None, "AMBIGUOUS_ORG"),      # 首选是 ACTIVE 也不替用户选
    (2, 5, "DISABLED", None, "AMBIGUOUS_ORG"),
])
def test_classify_memberships(count, first, status, org_id, state):
    r = classify_memberships(count, first, status)
    assert (r.org_id, r.state) == (org_id, state)


# ── 配置自洽 ──────────────────────────────────────────────

def _settings(**kw) -> Settings:
    base = {"JWT_SECRET_KEY": "x" * 32, "S2S_SHARED_SECRET": "", "FULFILLMENT_API_BASE_URL": ""}
    base.update(kw)
    return Settings(_env_file=None, **base)


def test_s2s_misconfigured_cases():
    assert s2s_misconfigured(_settings()) is None
    assert s2s_misconfigured(_settings(S2S_SHARED_SECRET="s" * 32, FULFILLMENT_API_BASE_URL="https://f.example")) is None
    assert s2s_misconfigured(_settings(S2S_SHARED_SECRET="s" * 32))
    assert s2s_misconfigured(_settings(FULFILLMENT_API_BASE_URL="https://f.example"))
    assert s2s_misconfigured(_settings(S2S_SHARED_SECRET="short", FULFILLMENT_API_BASE_URL="https://f.example"))
    assert s2s_misconfigured(_settings(S2S_SHARED_SECRET="s" * 32, FULFILLMENT_API_BASE_URL="f.example"))
    # 复用登录密钥 = 两个信任域塌成一个
    assert s2s_misconfigured(_settings(JWT_SECRET_KEY="j" * 40, S2S_SHARED_SECRET="j" * 40, FULFILLMENT_API_BASE_URL="https://f.example"))


@pytest.mark.parametrize("url", [
    "https://", "http://", "ftp://f.example", "f.example", "https:///path", "//f.example",
    "https://f.example/api/v1", "https://f.example/api/v1/", "https://f.example/?x=1", "https://f.example/#a",
])
def test_s2s_misconfigured_rejects_urls_without_scheme_or_host(url):
    """只看前缀不够:"https://" 过前缀检查后运行时 httpx 抛 InvalidURL(非 HTTPError)会变 500。"""
    assert s2s_misconfigured(_settings(S2S_SHARED_SECRET="s" * 32, FULFILLMENT_API_BASE_URL=url))


@pytest.mark.parametrize("url", ["https://f.example", "http://127.0.0.1:8000", "https://ops.example.com/"])
def test_s2s_misconfigured_accepts_full_urls(url):
    assert s2s_misconfigured(_settings(S2S_SHARED_SECRET="s" * 32, FULFILLMENT_API_BASE_URL=url)) is None

"""服务间(S2S)短时令牌:matgo ↔ 履约后台两向调用的签发与校验。

契约 docs/specs/2026-09-21-0214 §3。要点:
- 独立共享密钥 S2S_SHARED_SECRET,HS256 固定;禁用登录用的 decode_token(它不校 iss/aud)。
- 每次调用现签一枚:iss/aud/sub/typ/iat/exp/jti,exp−iat ≤ 60s。
- 接收方除 jose 的签名 / exp / aud / iss 校验外,自己再比较
  `0 < exp − iat ≤ 60` 与 `iat ≤ now + 30s`:否则签名方签一枚长效令牌就突破了所称的窗口。
- 真实可接受窗口(按接收方时钟):iat 最多超前 30s、TTL 60s、exp 再容忍 30s 偏差,
  三者叠加 = 一枚令牌最长 **120s** 内可被接受(契约按 60+30 写作 90s,漏算了未来 iat 那 30s)。
  两向都是只读 GET,且 exp 容差是契约要求(两主机时钟偏差),不去掉,如实记录。
- iss/aud 精确匹配是挡"同密钥反向重放"的唯一屏障。
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import NotAuthenticatedError

logger = logging.getLogger(__name__)

S2S_ALGORITHM = "HS256"
S2S_TYP = "s2s"
S2S_TTL_SECONDS = 60          # 令牌最长有效窗
S2S_CLOCK_SKEW_SECONDS = 30   # 两主机时钟偏差容忍

# 两向身份常量(与履约仓逐字一致)
ISS_MATGO = "matgo"
ISS_FULFILLMENT = "fulfillment"
AUD_FULFILLMENT_PORTAL = "fulfillment-portal"
AUD_MATGO_INTERNAL = "matgo-internal"
SUB_FULFILLMENT_SERVICE = "svc:fulfillment"

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class S2SPrincipal:
    """校验通过的服务调用方。与 CurrentUser 无继承关系:任何用户级守卫对它类型不匹配即拒。"""
    iss: str
    sub: str
    jti: str


class S2SError(JWTError):
    """令牌不合规(签名 / 时窗 / claim)。"""


def sign_s2s_token(*, iss: str, aud: str, sub: str, now: int | None = None) -> tuple[str, str]:
    """签发一枚短时令牌,返回 (token, jti)。jti 供调用方写日志。

    调用前置:settings.s2s_configured 为真;未配置由调用方决定如何拒绝,这里直接抛。
    """
    if not settings.S2S_SHARED_SECRET:
        raise S2SError("S2S_SHARED_SECRET not configured")
    iat = int(time.time()) if now is None else now
    jti = uuid.uuid4().hex
    payload = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "typ": S2S_TYP,
        "iat": iat,
        "exp": iat + S2S_TTL_SECONDS,
        "jti": jti,
    }
    return jwt.encode(payload, settings.S2S_SHARED_SECRET, algorithm=S2S_ALGORITHM), jti


def verify_s2s_token(
    token: str, *, issuer: str, audience: str, now: int | None = None
) -> S2SPrincipal:
    """按契约口径校验。失败抛 S2SError(JWTError 子类),不泄露具体原因给调用方。"""
    secret = settings.S2S_SHARED_SECRET
    if not secret:
        raise S2SError("S2S_SHARED_SECRET not configured")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[S2S_ALGORITHM],
            audience=audience,
            issuer=issuer,
            options={
                "require_exp": True,
                "require_iat": True,
                "require_sub": True,
                "require_jti": True,
                "require_aud": True,
                "require_iss": True,
                "leeway": S2S_CLOCK_SKEW_SECONDS,
            },
        )
    except JWTError as exc:
        raise S2SError(str(exc)) from exc

    if claims.get("typ") != S2S_TYP:
        raise S2SError("Wrong token typ")
    try:
        iat = int(claims["iat"])
        exp = int(claims["exp"])
    except (TypeError, ValueError) as exc:
        raise S2SError("iat/exp must be integers") from exc
    ttl = exp - iat
    if not (0 < ttl <= S2S_TTL_SECONDS):
        raise S2SError("Token lifetime out of bounds")
    current = int(time.time()) if now is None else now
    if iat > current + S2S_CLOCK_SKEW_SECONDS:
        raise S2SError("Token issued in the future")
    sub = claims["sub"]
    jti = claims["jti"]
    if not isinstance(sub, str) or not isinstance(jti, str) or not sub or not jti:
        raise S2SError("sub/jti must be non-empty strings")
    return S2SPrincipal(iss=str(claims["iss"]), sub=sub, jti=jti)


async def require_fulfillment_caller(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> S2SPrincipal:
    """内部路由守卫:只接受履约后台签发、面向 matgo-internal 的令牌。"""
    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise NotAuthenticatedError()
    try:
        principal = verify_s2s_token(
            creds.credentials, issuer=ISS_FULFILLMENT, audience=AUD_MATGO_INTERNAL
        )
    except JWTError as exc:
        logger.warning("s2s token rejected on internal route: %s", exc)
        raise NotAuthenticatedError("Invalid service token")
    logger.info("s2s call accepted iss=%s sub=%s jti=%s", principal.iss, principal.sub, principal.jti)
    return principal

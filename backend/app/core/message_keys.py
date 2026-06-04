"""系统消息 key 全集 — 前端翻译文件必须覆盖所有 key。

命名规范:error.<module>.<specific_error>
"""


class MessageKey:
    # auth
    INVALID_CREDENTIALS = "error.auth.invalid_credentials"
    ACCOUNT_LOCKED = "error.auth.account_locked"
    TOKEN_EXPIRED = "error.auth.token_expired"
    PERMISSION_DENIED = "error.auth.permission_denied"
    NOT_AUTHENTICATED = "error.auth.not_authenticated"

    # validation
    VALIDATION_FAILED = "error.validation.failed"

    # general
    NOT_FOUND = "error.general.not_found"
    INTERNAL_ERROR = "error.general.internal_error"
    RATE_LIMITED = "error.general.rate_limited"
    CONFLICT = "error.general.conflict"

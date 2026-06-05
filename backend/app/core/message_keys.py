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

    ACCOUNT_DISABLED = "error.auth.account_disabled"
    PASSWORD_CHANGE_REQUIRED = "error.auth.password_change_required"

    # validation
    VALIDATION_FAILED = "error.validation.failed"
    MULTIPLE_VALIDATION_ERRORS = "error.validation.multiple_errors"

    # general
    NOT_FOUND = "error.general.not_found"
    INTERNAL_ERROR = "error.general.internal_error"
    RATE_LIMITED = "error.general.rate_limited"
    CONFLICT = "error.general.conflict"

    # business
    SUPPLIER_ALREADY_REGISTERED = "error.business.supplier_already_registered"
    EMAIL_ALREADY_REGISTERED = "error.business.email_already_registered"
    PHONE_ALREADY_REGISTERED = "error.business.phone_already_registered"

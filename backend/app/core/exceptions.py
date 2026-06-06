"""业务异常 + 统一响应格式。

业务码(body.code)与 HTTP status 解耦,仅承载业务语义。

格式 5 位:C MM SS
- C : 4=客户端类, 5=服务端类
- MM: 模块段
- SS: 模块内顺序号(01–99)

模块段位:
  MM | 模块             | 现有码
  00 | 通用与鉴权       | 40001–40009
  01 | 供应商(注册/资质) | 预留
  02 | 商品             | 预留
  03 | 品类             | 预留
  04 | 信用             | 预留(credit 类型化时填)
  05–08 | 预留           | —
  09 | 注册冲突聚合     | 40901/40902/40903(前端冻结,沿用)

兜底码:
  40000 = 通用客户端兜底(裸 HTTPException 降级)
  50000 = 通用服务端兜底(未处理异常)

既存例外(不纳入 4MMSS,标注为 422 派生):
  42200 = 请求体校验失败(handler 级,前端冻结)

成功码: 0
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.core.message_keys import MessageKey


class BusinessError(HTTPException):
    """所有业务异常的基类。"""

    def __init__(
        self,
        http_status: int,
        biz_code: int,
        message: str,
        data: Any = None,
        message_key: str | None = None,
        message_params: dict | None = None,
    ):
        super().__init__(status_code=http_status, detail=message)
        self.biz_code = biz_code
        self.biz_message = message
        self.biz_data = data
        self.message_key = message_key
        self.message_params = message_params


class InvalidCredentialsError(BusinessError):
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, 40001, message, message_key=MessageKey.INVALID_CREDENTIALS)


class TooManyAttemptsError(BusinessError):
    def __init__(self, message: str = "Too many failed attempts, account locked"):
        super().__init__(status.HTTP_429_TOO_MANY_REQUESTS, 40002, message, message_key=MessageKey.ACCOUNT_LOCKED)


class PermissionDeniedError(BusinessError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(status.HTTP_403_FORBIDDEN, 40003, message, message_key=MessageKey.PERMISSION_DENIED)


class NotAuthenticatedError(BusinessError):
    def __init__(self, message: str = "Not authenticated"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, 40004, message, message_key=MessageKey.NOT_AUTHENTICATED)


class AccountDisabledError(BusinessError):
    def __init__(self, message: str = "Account disabled"):
        super().__init__(status.HTTP_403_FORBIDDEN, 40005, message, message_key=MessageKey.ACCOUNT_DISABLED)


class ValidationFailedError(BusinessError):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(status.HTTP_400_BAD_REQUEST, 40006, message, message_key=MessageKey.VALIDATION_FAILED)


class PasswordChangeRequiredError(BusinessError):
    """must_change_password=True 的账号访问非豁免端点时抛出。"""

    def __init__(self, message: str = "Password change required"):
        super().__init__(status.HTTP_403_FORBIDDEN, 40007, message, message_key=MessageKey.PASSWORD_CHANGE_REQUIRED)


class ConflictError(BusinessError):
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(status.HTTP_409_CONFLICT, 40009, message, message_key=MessageKey.CONFLICT)


class SupplierAlreadyRegisteredError(BusinessError):
    """供应商重复入驻(PRD v1.4 Δ9)。

    code=40901(数字),前端识别错误必须用数字比较,严禁字符串比较异常类名。
    message 沿用 PRD v1.3 §5.3 标准化文案,不暴露 owner / 公司名。
    """

    def __init__(
        self,
        message: str = "当前企业已在平台注册。如需加入,请联系您所在企业的平台管理员添加账号。",
    ):
        super().__init__(status.HTTP_409_CONFLICT, 40901, message, message_key=MessageKey.SUPPLIER_ALREADY_REGISTERED)


class EmailAlreadyRegisteredError(BusinessError):
    """邮箱已被注册(PRD v1.5 Δ2,code=40902)。单独抛出场景。"""

    def __init__(
        self,
        message: str = "该邮箱已注册,请直接登录或更换邮箱",
    ):
        super().__init__(
            status.HTTP_409_CONFLICT,
            40902,
            message,
            data={"errors": [{"field": "email", "code": 40902, "message": message}]},
            message_key=MessageKey.EMAIL_ALREADY_REGISTERED,
        )


class PhoneAlreadyRegisteredError(BusinessError):
    """手机号已被注册(PRD v1.5 Δ2,code=40903)。单独抛出场景。"""

    def __init__(
        self,
        message: str = "该手机号已注册,请直接登录或更换手机号",
    ):
        super().__init__(
            status.HTTP_409_CONFLICT,
            40903,
            message,
            data={"errors": [{"field": "phone", "code": 40903, "message": message}]},
            message_key=MessageKey.PHONE_ALREADY_REGISTERED,
        )


class MultipleValidationError(BusinessError):
    """多错误并发场景(PRD v1.5 Δ3)。
    顶层 code 按优先级取:40901(注册号重) > 40902(邮箱重) > 40903(手机号重)。
    无论 errors 长度为 1 还是 N,response.data.errors 都返回数组。
    """

    # 数字优先级:索引小者优先,作为顶层 code 来源
    _PRIORITY = (40901, 40902, 40903)

    def __init__(self, errors: list[dict]):
        if not errors:
            # 业务上不该走到这里;防御性兜底
            raise ValueError("MultipleValidationError requires at least one error")
        # 取优先级最高的错误码作为顶层 code
        codes = {e["code"] for e in errors}
        top_code = next((c for c in self._PRIORITY if c in codes), errors[0]["code"])
        if len(errors) == 1:
            top_message = errors[0]["message"]
        else:
            top_message = "请修正以下问题"
        super().__init__(
            status.HTTP_409_CONFLICT,
            top_code,
            top_message,
            data={"errors": errors},
            message_key=MessageKey.MULTIPLE_VALIDATION_ERRORS,
        )


class NotFoundError(BusinessError):
    def __init__(self, message: str = "Not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, 40008, message, message_key=MessageKey.NOT_FOUND)


def success(data: Any = None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}

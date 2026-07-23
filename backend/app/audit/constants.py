"""审计资源类型与操作枚举。"""
from __future__ import annotations

from enum import Enum


class AuditResourceType(str, Enum):
    AUTH = "auth"
    USER = "user"
    ROLE = "role"
    PERMISSION = "permission"
    USER_ROLE = "user_role"
    BUYER_ORG = "buyer_org"
    SUPPLIER_ORG = "supplier_org"
    BUYER_MEMBER = "buyer_member"
    SUPPLIER_MEMBER = "supplier_member"
    PRODUCT = "product"
    PRODUCT_SKU = "product_sku"
    CART = "cart"
    RFQ = "rfq"
    QUOTE = "quote"
    ATTACHMENT = "attachment"
    INGEST_RUN = "ingest_run"
    ZONE_GRANT = "zone_grant"
    BANNER = "banner"


class AuditAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DISABLE = "DISABLE"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGIN_LOCKED = "LOGIN_LOCKED"
    LOGOUT = "LOGOUT"
    REGISTER = "REGISTER"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    PASSWORD_RESET = "PASSWORD_RESET"    # 忘记密码流程重置(未登录,验证码校验通过)
    # 自助资料变更(用户对自己账号的操作)
    PROFILE_UPDATE = "PROFILE_UPDATE"   # 改 name/phone 等低风险字段
    EMAIL_CHANGE = "EMAIL_CHANGE"       # 改登录邮箱
    USERNAME_CHANGE = "USERNAME_CHANGE" # 改/清空登录用户名
    PHONE_CHANGE = "PHONE_CHANGE"       # 改/清空登录手机号
    USER_DISABLE = "USER_DISABLE"       # ADMIN 停用账号
    USER_ENABLE = "USER_ENABLE"         # ADMIN 启用账号
    FORCE_LOGOUT = "FORCE_LOGOUT"     # 管理员强制下线(bump token_version)
    REFRESH_REPLAY = "REFRESH_REPLAY"  # refresh token 重放检测(会话被杀)
    ROLE_ASSIGN = "ROLE_ASSIGN"
    ROLE_REVOKE = "ROLE_REVOKE"
    STATUS_CHANGE = "STATUS_CHANGE"
    # cart — 购物车操作
    ADD_ITEM = "ADD_ITEM"
    UPDATE_ITEM = "UPDATE_ITEM"
    REMOVE_ITEM = "REMOVE_ITEM"
    CLEAR = "CLEAR"
    # rfq — 询价单操作
    SUBMIT = "SUBMIT"
    PROXY_CREATE = "PROXY_CREATE"
    CANCEL = "CANCEL"
    CLAIM = "CLAIM"
    WITHDRAW = "WITHDRAW"
    # rfq — 决策操作(RFQ 资源)
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    # quote — 报价操作(QUOTE 资源)
    BACKFILL = "BACKFILL"
    REQUOTE = "REQUOTE"
    EXPIRE = "EXPIRE"
    # attachment — 附件操作
    UPLOAD = "UPLOAD"
    # ingest — 商品导入
    IMPORT = "IMPORT"

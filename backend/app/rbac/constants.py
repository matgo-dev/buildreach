"""权限点常量。

设计原则(v3 §0.3):
- 权限点回答"能不能做某个动作",**不带 scope 后缀**(禁止 `:own` / `:all` / `:org`)
- 数据范围由 scope_config.py 单独管理
- auth:* 是系统底层会话权限,不在业务矩阵内,但仍参与启动同步
"""
from __future__ import annotations


class Permissions:
    """所有权限点。v3 标准:`<resource>:<action>`,不带 scope 后缀。"""

    # ----- 系统底层会话(独立于业务矩阵)-----
    AUTH_LOGIN = "auth:login"
    AUTH_LOGOUT = "auth:logout"
    AUTH_ME = "auth:me"

    # ----- 业务-档案:supplier -----
    SUPPLIER_READ = "supplier:read"
    SUPPLIER_WRITE = "supplier:write"
    SUPPLIER_APPROVE = "supplier:approve"
    SUPPLIER_REJECT = "supplier:reject"

    # ----- 业务-档案:product -----
    PRODUCT_READ = "product:read"
    PRODUCT_WRITE = "product:write"
    PRODUCT_APPROVE = "product:approve"
    PRODUCT_REJECT = "product:reject"

    # ----- 业务-档案:country -----
    COUNTRY_READ = "country:read"
    COUNTRY_WRITE = "country:write"

    # ----- 业务-档案:credit(信用评估)-----
    CREDIT_READ = "credit:read"
    CREDIT_WRITE = "credit:write"
    CREDIT_RECOMPUTE = "credit:recompute"

    # ----- 业务-交易:project -----
    PROJECT_READ = "project:read"
    PROJECT_WRITE = "project:write"

    # ----- 业务-交易:purchase_list -----
    PURCHASE_LIST_READ = "purchase_list:read"
    PURCHASE_LIST_WRITE = "purchase_list:write"

    # ----- 业务-交易:cart -----
    CART_READ = "cart:read"
    CART_WRITE = "cart:write"

    # ----- 业务-交易:rfq -----
    RFQ_READ = "rfq:read"
    RFQ_CREATE = "rfq:create"
    RFQ_RESPOND = "rfq:respond"

    # ----- 业务-交易:quote -----
    QUOTE_READ = "quote:read"
    QUOTE_WRITE = "quote:write"

    # ----- 业务-交易:order(含 12 节点履约 + 单据)-----
    ORDER_READ = "order:read"
    ORDER_WRITE = "order:write"
    ORDER_CHECKIN = "order:checkin"

    # ----- 业务-供应商:membership -----
    MEMBERSHIP_READ = "membership:read"
    MEMBERSHIP_WRITE = "membership:write"

    # ----- 业务-运营:risk -----
    RISK_READ = "risk:read"

    # ----- 系统:user / role / permission / system -----
    USER_MANAGE = "user:manage"
    ROLE_MANAGE = "role:manage"
    PERMISSION_MANAGE = "permission:manage"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_AUDIT = "system:audit"


# auth:* 是系统底层会话权限,不归任何资源域(供启动同步识别,不进矩阵)
SYSTEM_RESERVED_CODES = frozenset({
    Permissions.AUTH_LOGIN,
    Permissions.AUTH_LOGOUT,
    Permissions.AUTH_ME,
})


class ModuleLabel:
    """资源域 module 标签(用于侧边栏分组)。"""
    BIZ_ARCHIVE = "业务-档案"
    BIZ_TRADE = "业务-交易"
    BIZ_SUPPLIER = "业务-供应商"
    BIZ_OPERATION = "业务-运营"
    SYSTEM = "系统"
    AUTH = "auth"


# 权限点元数据(用于启动同步:name / module)
PERMISSION_META: dict[str, dict[str, str]] = {
    Permissions.AUTH_LOGIN: {"name": "登录", "module": ModuleLabel.AUTH},
    Permissions.AUTH_LOGOUT: {"name": "登出", "module": ModuleLabel.AUTH},
    Permissions.AUTH_ME: {"name": "获取当前用户", "module": ModuleLabel.AUTH},

    Permissions.SUPPLIER_READ: {"name": "查看供应商档案", "module": ModuleLabel.BIZ_ARCHIVE},
    Permissions.SUPPLIER_WRITE: {"name": "编辑供应商档案", "module": ModuleLabel.BIZ_ARCHIVE},
    Permissions.SUPPLIER_APPROVE: {"name": "审核通过供应商", "module": ModuleLabel.BIZ_ARCHIVE},
    Permissions.SUPPLIER_REJECT: {"name": "驳回供应商", "module": ModuleLabel.BIZ_ARCHIVE},

    Permissions.PRODUCT_READ: {"name": "查看商品 SKU", "module": ModuleLabel.BIZ_ARCHIVE},
    Permissions.PRODUCT_WRITE: {"name": "编辑商品 SKU", "module": ModuleLabel.BIZ_ARCHIVE},
    Permissions.PRODUCT_APPROVE: {"name": "审核通过商品", "module": ModuleLabel.BIZ_ARCHIVE},
    Permissions.PRODUCT_REJECT: {"name": "驳回商品", "module": ModuleLabel.BIZ_ARCHIVE},

    Permissions.COUNTRY_READ: {"name": "查看国别准入", "module": ModuleLabel.BIZ_ARCHIVE},
    Permissions.COUNTRY_WRITE: {"name": "维护国别准入", "module": ModuleLabel.BIZ_ARCHIVE},

    Permissions.CREDIT_READ: {"name": "查看信用评估", "module": ModuleLabel.BIZ_ARCHIVE},
    Permissions.CREDIT_WRITE: {"name": "维护信用评估档案", "module": ModuleLabel.BIZ_ARCHIVE},
    Permissions.CREDIT_RECOMPUTE: {"name": "触发评分重算", "module": ModuleLabel.BIZ_ARCHIVE},

    Permissions.PROJECT_READ: {"name": "查看项目", "module": ModuleLabel.BIZ_TRADE},
    Permissions.PROJECT_WRITE: {"name": "管理项目", "module": ModuleLabel.BIZ_TRADE},

    Permissions.PURCHASE_LIST_READ: {"name": "查看采购清单", "module": ModuleLabel.BIZ_TRADE},
    Permissions.PURCHASE_LIST_WRITE: {"name": "管理采购清单", "module": ModuleLabel.BIZ_TRADE},

    Permissions.CART_READ: {"name": "查看购物车", "module": ModuleLabel.BIZ_TRADE},
    Permissions.CART_WRITE: {"name": "管理购物车", "module": ModuleLabel.BIZ_TRADE},

    Permissions.RFQ_READ: {"name": "查看询价单", "module": ModuleLabel.BIZ_TRADE},
    Permissions.RFQ_CREATE: {"name": "发起询价单", "module": ModuleLabel.BIZ_TRADE},
    Permissions.RFQ_RESPOND: {"name": "响应询价单", "module": ModuleLabel.BIZ_TRADE},

    Permissions.QUOTE_READ: {"name": "查看报价", "module": ModuleLabel.BIZ_TRADE},
    Permissions.QUOTE_WRITE: {"name": "提交报价", "module": ModuleLabel.BIZ_TRADE},

    Permissions.ORDER_READ: {"name": "查看订单", "module": ModuleLabel.BIZ_TRADE},
    Permissions.ORDER_WRITE: {"name": "管理订单", "module": ModuleLabel.BIZ_TRADE},
    Permissions.ORDER_CHECKIN: {"name": "订单节点打卡", "module": ModuleLabel.BIZ_TRADE},

    Permissions.MEMBERSHIP_READ: {"name": "查看会员", "module": ModuleLabel.BIZ_SUPPLIER},
    Permissions.MEMBERSHIP_WRITE: {"name": "管理会员", "module": ModuleLabel.BIZ_SUPPLIER},

    Permissions.RISK_READ: {"name": "风控驾驶舱", "module": ModuleLabel.BIZ_OPERATION},

    Permissions.USER_MANAGE: {"name": "用户管理", "module": ModuleLabel.SYSTEM},
    Permissions.ROLE_MANAGE: {"name": "角色管理", "module": ModuleLabel.SYSTEM},
    Permissions.PERMISSION_MANAGE: {"name": "权限管理", "module": ModuleLabel.SYSTEM},
    Permissions.SYSTEM_CONFIG: {"name": "系统配置", "module": ModuleLabel.SYSTEM},
    Permissions.SYSTEM_AUDIT: {"name": "审计日志", "module": ModuleLabel.SYSTEM},
}


ROLE_META: dict[str, dict[str, str]] = {
    "BUYER": {"name": "项目部采购员", "description": "采购方项目部成员"},
    "SUPPLIER": {"name": "供应商", "description": "海外材料供货方"},
    "OPERATOR": {"name": "平台运营", "description": "平台业务管理员,业务全量访问 + 审核"},
    "ADMIN": {"name": "系统管理员", "description": "系统级管理员,不触业务数据(Q25)"},
}

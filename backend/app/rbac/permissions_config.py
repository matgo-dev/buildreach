"""角色 → 权限点 分配表(v3 §3 权威清单)。

设计原则:
- 权限点 code 不带 scope 后缀(:own/:all/:org 禁止)
- 4 角色拿到的是同一个 code,差异由 scope_config.py 决定
- auth:* 给所有角色(系统底层会话)

# TODO(Q22): 角色-权限关系定义方式 — 当前实现:配置文件 + 启动同步(方案 C)
# TODO(Q25): ADMIN 严格不触业务数据(本配置严格遵守)
"""
from __future__ import annotations

from app.rbac.constants import Permissions

# 所有角色都需要的会话权限(auth:*)
_AUTH_BASE = [
    Permissions.AUTH_LOGIN,
    Permissions.AUTH_LOGOUT,
    Permissions.AUTH_ME,
]

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "BUYER": [
        *_AUTH_BASE,
        # 公开池(read)
        Permissions.SUPPLIER_READ,
        Permissions.PRODUCT_READ,
        Permissions.COUNTRY_READ,
        # 采购流程
        Permissions.PROJECT_READ,
        Permissions.PROJECT_WRITE,
        Permissions.PURCHASE_LIST_READ,
        Permissions.PURCHASE_LIST_WRITE,
        Permissions.CART_READ,
        Permissions.CART_WRITE,
        Permissions.RFQ_READ,
        Permissions.RFQ_CREATE,
        Permissions.QUOTE_READ,
        Permissions.ORDER_READ,
        Permissions.ORDER_WRITE,
        # 信用评估 — 仅查看(工单 §3.7)
        Permissions.CREDIT_READ,
    ],
    "SUPPLIER": [
        *_AUTH_BASE,
        # 自家档案 + 公开池
        Permissions.SUPPLIER_READ,
        Permissions.SUPPLIER_WRITE,
        Permissions.PRODUCT_READ,
        Permissions.PRODUCT_WRITE,
        Permissions.COUNTRY_READ,
        # 响应业务
        Permissions.RFQ_READ,
        Permissions.RFQ_RESPOND,
        Permissions.QUOTE_READ,
        Permissions.QUOTE_WRITE,
        Permissions.ORDER_READ,
        Permissions.ORDER_WRITE,
        Permissions.ORDER_CHECKIN,
        Permissions.MEMBERSHIP_READ,
        Permissions.MEMBERSHIP_WRITE,
        # 信用评估:SUPPLIER 不持有任何 credit 权限点(Δ5 定位变更:评估对象=Supplier,
        # SUPPLIER 暂不可看自家评分;调任何 credit 接口 → 403)
    ],
    "OPERATOR": [
        *_AUTH_BASE,
        # 业务全量(scope=ALL)
        Permissions.SUPPLIER_READ,
        Permissions.SUPPLIER_APPROVE,
        Permissions.SUPPLIER_REJECT,
        Permissions.PRODUCT_READ,
        Permissions.PRODUCT_APPROVE,
        Permissions.PRODUCT_REJECT,
        Permissions.COUNTRY_READ,
        Permissions.COUNTRY_WRITE,
        Permissions.PROJECT_READ,
        Permissions.PURCHASE_LIST_READ,
        Permissions.RFQ_READ,
        Permissions.QUOTE_READ,
        Permissions.ORDER_READ,
        Permissions.MEMBERSHIP_READ,
        Permissions.RISK_READ,
        # 信用评估 — 全权(读 / 写 / 触发重算)
        Permissions.CREDIT_READ,
        Permissions.CREDIT_WRITE,
        Permissions.CREDIT_RECOMPUTE,
    ],
    "ADMIN": [
        *_AUTH_BASE,
        # 系统级,严格不触业务(Q25 + RBAC 规范 §4.3 / §8.6 职责分离)
        # ADMIN 不持有任何 credit:* 权限点 — require_permission 阶段直接 403
        Permissions.USER_MANAGE,
        Permissions.ROLE_MANAGE,
        Permissions.PERMISSION_MANAGE,
        Permissions.SYSTEM_CONFIG,
        Permissions.SYSTEM_AUDIT,
    ],
}

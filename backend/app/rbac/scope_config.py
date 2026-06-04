"""数据范围(scope)配置 + 查表函数。

v3 §4 设计:
- 权限点回答"能不能做",scope 回答"看哪些数据"
- scope 是简单查表 (角色, 资源域) → ALL/ORG/OWN/NONE
- 不做策略引擎、不支持优先级、不支持表达式 DSL

资源域权威清单(v3 §2 + 信用评估 §六):16 个
  supplier / product / country / credit
  project / purchase_list / cart
  rfq / quote / order / membership / risk
  user / role / permission / system
"""
from __future__ import annotations

from enum import Enum


class Scope(str, Enum):
    """数据范围。"""
    ALL = "ALL"       # 全平台数据(无 WHERE 过滤)
    ORG = "ORG"       # 本组织数据(BUYER 按 buyer_organization_id 过滤)
    OWN = "OWN"       # 本人/本企业数据(SUPPLIER 按 supplier_id 过滤)
    NONE = "NONE"     # 无访问权


# 资源域 → 中文名 / module 标签
RESOURCES: dict[str, dict[str, str]] = {
    "supplier":       {"name": "供应商档案", "module": "业务-档案"},
    "product":        {"name": "商品 SKU",   "module": "业务-档案"},
    "country":        {"name": "国别准入",   "module": "业务-档案"},
    "credit":         {"name": "信用评估",   "module": "业务-档案"},
    "project":        {"name": "项目",       "module": "业务-交易"},
    "purchase_list":  {"name": "采购清单",   "module": "业务-交易"},
    "cart":           {"name": "购物车",     "module": "业务-交易"},
    "rfq":            {"name": "询价单",     "module": "业务-交易"},
    "quote":          {"name": "报价",       "module": "业务-交易"},
    "order":          {"name": "订单",       "module": "业务-交易"},
    "membership":     {"name": "会员",       "module": "业务-供应商"},
    "risk":           {"name": "风控驾驶舱", "module": "业务-运营"},
    "user":           {"name": "用户管理",   "module": "系统"},
    "role":           {"name": "角色管理",   "module": "系统"},
    "permission":     {"name": "权限管理",   "module": "系统"},
    "system":         {"name": "系统配置",   "module": "系统"},
}


# 角色 × 资源域 → scope 值(v3 §4 权威表)
#
# ---- 业务粒度决策(2026-05-18 拍板,等业务流程 3 上线时遵循)----
# Q:BUYER 看到的项目/采购清单/订单 范围是?
# A:方案 A —— 同组织内所有数据(scope=ORG)
#    含义:中建三局任一 BUYER 登录,能看到中建三局所有 BUYER 创建的所有项目
#    实现:service 层 WHERE buyer_organization_id = current_user.organization_id
#    暂不实现:项目成员制(B 方案) / 项目内角色制(C 方案);后续按需加 project_members 表
# ----------------------------------------------------------------
ROLE_RESOURCE_SCOPE: dict[str, dict[str, Scope]] = {
    "BUYER": {
        "supplier":      Scope.ALL,
        "product":       Scope.ALL,
        "country":       Scope.ALL,
        "credit":        Scope.ALL,
        "project":       Scope.ORG,
        "purchase_list": Scope.ORG,
        "cart":          Scope.OWN,
        "rfq":           Scope.ORG,
        "quote":         Scope.ORG,
        "order":         Scope.ORG,
        "membership":    Scope.NONE,
        "risk":          Scope.NONE,
        "user":          Scope.NONE,
        "role":          Scope.NONE,
        "permission":    Scope.NONE,
        "system":        Scope.NONE,
    },
    "SUPPLIER": {
        "supplier":      Scope.OWN,
        "product":       Scope.OWN,
        "country":       Scope.ALL,
        # 信用评估:Δ5 定位变更后 SUPPLIER 不持有 credit 权限点,scope 同步 NONE
        # (SUPPLIER 暂不可看自家评分,API 层 require_permission 直接 403)
        "credit":        Scope.NONE,
        "project":       Scope.NONE,
        "purchase_list": Scope.NONE,
        "cart":          Scope.NONE,
        "rfq":           Scope.OWN,
        "quote":         Scope.OWN,
        "order":         Scope.OWN,
        "membership":    Scope.OWN,
        "risk":          Scope.NONE,
        "user":          Scope.NONE,
        "role":          Scope.NONE,
        "permission":    Scope.NONE,
        "system":        Scope.NONE,
    },
    "OPERATOR": {
        "supplier":      Scope.ALL,
        "product":       Scope.ALL,
        "country":       Scope.ALL,
        "credit":        Scope.ALL,
        "project":       Scope.ALL,
        "purchase_list": Scope.ALL,
        "cart":          Scope.NONE,
        "rfq":           Scope.ALL,
        "quote":         Scope.ALL,
        "order":         Scope.ALL,
        "membership":    Scope.ALL,
        "risk":          Scope.ALL,
        "user":          Scope.NONE,
        "role":          Scope.NONE,
        "permission":    Scope.NONE,
        "system":        Scope.NONE,
    },
    "ADMIN": {
        "supplier":      Scope.NONE,
        "product":       Scope.NONE,
        "country":       Scope.NONE,
        # 信用评估:ADMIN 严格不触业务数据(Q25 + RBAC 规范 §4.3 / §8.6 职责分离)
        # 权限点已在 permissions_config.py 中不授予,scope 这里同步 NONE 兜底
        "credit":        Scope.NONE,
        "project":       Scope.NONE,
        "purchase_list": Scope.NONE,
        "cart":          Scope.NONE,
        "rfq":           Scope.NONE,
        "quote":         Scope.NONE,
        "order":         Scope.NONE,
        "membership":    Scope.NONE,
        "risk":          Scope.NONE,
        "user":          Scope.ALL,
        "role":          Scope.ALL,
        "permission":    Scope.ALL,
        "system":        Scope.ALL,
    },
}


def get_scope(role_codes: list[str], resource: str) -> Scope:
    """根据用户角色 + 资源域查 scope。多角色取**最宽松**(ALL > ORG > OWN > NONE)。"""
    if resource not in RESOURCES:
        return Scope.NONE
    rank = {Scope.NONE: 0, Scope.OWN: 1, Scope.ORG: 2, Scope.ALL: 3}
    best = Scope.NONE
    for r in role_codes:
        s = ROLE_RESOURCE_SCOPE.get(r, {}).get(resource, Scope.NONE)
        if rank[s] > rank[best]:
            best = s
    return best


def explain_scope(scope: Scope, resource: str) -> str:
    """生成 scope 的中文解释 + SQL 示例。"""
    name = RESOURCES.get(resource, {}).get("name", resource)
    if scope == Scope.ALL:
        return f"全平台 {name} 数据,无 WHERE 过滤"
    if scope == Scope.ORG:
        return f"仅本采购组织的 {name},service 层强制 WHERE buyer_organization_id = current_user.organization_id"
    if scope == Scope.OWN:
        return f"仅本企业/本人的 {name},service 层强制 WHERE supplier_id = current_user.supplier_id 或 user_id = current_user.id"
    return f"无访问权(权限点拦截不应走到 service 层)"


def would_apply_filter(scope: Scope, organization_id: int | None) -> str:
    """生成示例 SQL WHERE 字符串(展示用,不真实执行)。"""
    if scope == Scope.ALL:
        return "(no filter — 全平台)"
    if scope == Scope.ORG:
        return f"WHERE buyer_organization_id = {organization_id if organization_id is not None else 'NULL'}"
    if scope == Scope.OWN:
        return f"WHERE supplier_id = {organization_id if organization_id is not None else 'NULL'} OR user_id = current_user.id"
    return "(blocked at permission check)"


# 各资源域的"主要 read 权限点"(供调试接口 permission_check 使用)
RESOURCE_PRIMARY_READ: dict[str, str] = {
    "supplier":      "supplier:read",
    "product":       "product:read",
    "country":       "country:read",
    "credit":        "credit:read",
    "project":       "project:read",
    "purchase_list": "purchase_list:read",
    "cart":          "cart:read",
    "rfq":           "rfq:read",
    "quote":         "quote:read",
    "order":         "order:read",
    "membership":    "membership:read",
    "risk":          "risk:read",
    "user":          "user:manage",
    "role":          "role:manage",
    "permission":    "permission:manage",
    "system":        "system:config",
}

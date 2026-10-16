"""专区导入脚本共用:--commit 守卫。

两个专区脚本(央企 import_zone_soe_materials / 矿业 import_zone_mining)共用一份,
别各自复制——守卫改一次要两边同时生效。
"""
from __future__ import annotations

import os

from sqlalchemy.engine.url import make_url

OPT_IN_ENV = "ALLOW_ZONE_IMPORT_PROD"
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def commit_needs_opt_in(database_url: str | None) -> bool:
    """只有 DB 主机是本机回环地址才免显式确认。

    以前按"URL 含 OVH 公网 IP"判生产,但 README 要求 ops 在 OVH 容器里跑脚本,容器里
    DATABASE_URL 的主机是 compose 服务名,守卫根本不触发。现在反过来:非本机一律要确认,
    staging 容器也要带 ALLOW_ZONE_IMPORT_PROD=1,宁可多敲一个环境变量。
    """
    if not database_url:
        return True
    try:
        host = make_url(database_url).host
    except Exception:
        return True
    return (host or "").lower() not in _LOCAL_HOSTS


def guard_commit(database_url: str | None, *, dry_run: bool) -> None:
    """--commit 且 DB 不在本机 → 必须 ALLOW_ZONE_IMPORT_PROD=1,否则 SystemExit。dry-run 不拦。"""
    if dry_run:
        return
    if commit_needs_opt_in(database_url) and os.environ.get(OPT_IN_ENV) != "1":
        raise SystemExit(
            f"拒绝执行:DATABASE_URL 指向非本机数据库(staging/生产)。先备份并 dry-run,"
            f"确认后设 {OPT_IN_ENV}=1 再 --commit。"
        )

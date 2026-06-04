"""Tavily + LLM 侧简易文件缓存(爬虫侧不缓存)。"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


class SimpleCache:
    """文件级 KV 缓存,按 (namespace, company_name) 做 key。"""

    def __init__(self, cache_dir: str, ttl_hours: int):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600

    def _key(self, namespace: str, company_name: str) -> Path:
        h = hashlib.md5(f"{namespace}:{company_name}".encode()).hexdigest()
        return self.cache_dir / f"{h}.json"

    def get(self, namespace: str, company_name: str) -> dict | None:
        path = self._key(namespace, company_name)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        if time.time() - data.get("ts", 0) > self.ttl_seconds:
            return None
        return data.get("payload")

    def set(self, namespace: str, company_name: str, payload: dict) -> None:
        # 确保目录存在(防目录被外部删除后 singleton 不重建)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._key(namespace, company_name)
        path.write_text(json.dumps({"ts": time.time(), "payload": payload}, default=str))

    def clear_company(self, company_name: str) -> None:
        """清该公司所有维度缓存(强制刷新用)。"""
        for ns in ("basic_tavily", "legal_tavily"):
            self._key(ns, company_name).unlink(missing_ok=True)


_cache_singleton: SimpleCache | None = None


def get_cache() -> SimpleCache:
    global _cache_singleton
    if _cache_singleton is None:
        from config import settings
        _cache_singleton = SimpleCache(settings.CACHE_DIR, settings.CACHE_TTL_HOURS)
    return _cache_singleton

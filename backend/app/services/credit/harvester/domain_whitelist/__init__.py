"""按国别加载域名白名单配置(Δ7 v0.3)。

domain_whitelist/<country_code>.yaml 是业务知识资产,记录"每国每维度哪些数据源最权威"。
后续国别扩展只需新增 YAML 文件,无需改代码。
"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_WHITELIST_DIR = Path(__file__).parent


def load_whitelist(country_code: str, dimension: str) -> list[str]:
    """加载指定国家、指定维度的域名白名单。

    未配置的国家 / 维度返回空列表;YAML 解析失败也返回空列表并记日志
    (调用方据此降级为全网搜索,不阻塞抓取)。
    """
    yaml_path = _WHITELIST_DIR / f"{country_code.lower()}.yaml"
    if not yaml_path.exists():
        return []
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("域名白名单 %s 加载失败,降级全网搜索: %s", yaml_path.name, exc)
        return []
    value = config.get(dimension, [])
    return value if isinstance(value, list) else []

"""SKU 计量单位枚举 code — 单一来源。

DB 存中性大写 ASCII code，前端 next-intl 文案负责多语言显示。
扩展方式：加 code + 加前端文案。
"""
from typing import Literal

SKU_UNITS = (
    "PCS",      # 件 / 个 / 支 / 台
    "SET",      # 套
    "PAIR",     # 双 / 对
    "M",        # 米
    "M2",       # 平方米
    "M3",       # 立方米
    "KG",       # 千克
    "TON",      # 吨
    "ROLL",     # 卷
    "SHEET",    # 张 / 片
    "BOX",      # 箱 / 盒
    "BAG",      # 袋
    "BARREL",   # 桶
    "L",        # 升
    "BUNDLE",   # 捆
)

SkuUnitCode = Literal[
    "PCS", "SET", "PAIR", "M", "M2", "M3", "KG", "TON",
    "ROLL", "SHEET", "BOX", "BAG", "BARREL", "L", "BUNDLE",
]

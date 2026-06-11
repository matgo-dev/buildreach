"""报价贸易术语 / 币种枚举码 — 单一来源。

DB 存中性大写 ASCII code，前端 next-intl 文案负责多语言显示。
扩展方式：加 code + 加前端文案。
"""
from typing import Literal

TRADE_TERMS = ("FOB", "CFR", "CIF")

TradeTermCode = Literal["FOB", "CFR", "CIF"]

CURRENCIES = ("USD", "CNY", "TZS")

CurrencyCode = Literal["USD", "CNY", "TZS"]

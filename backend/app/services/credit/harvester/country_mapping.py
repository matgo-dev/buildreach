"""国别代码到 Tavily country 参数的映射(Δ7 v0.3)。

Tavily country 参数取值为国家名(小写英文),不是 ISO 国别代码。
本期只映射柬埔寨,后续逐国扩展。
"""
from __future__ import annotations

# 9 国扩展时逐步补充
COUNTRY_CODE_TO_TAVILY_COUNTRY: dict[str, str] = {
    "KH": "cambodia",
    # "MY": "malaysia",
    # "PK": "pakistan",
    # "ID": "indonesia",
    # "SA": "saudi arabia",
    # "AE": "united arab emirates",
    # "MA": "morocco",
    # "IQ": "iraq",
    # "CN": "china",
}


def get_tavily_country(country_code: str) -> str | None:
    """根据 ISO 国别代码获取 Tavily country 参数取值。

    未配置的国家返回 None,Tavily 调用时不传 country 参数(全网搜索)。
    """
    return COUNTRY_CODE_TO_TAVILY_COUNTRY.get((country_code or "").upper())

"""供应商注册:9 国常量(前后端必须对齐部分)。

边界(PRD v1.3 §5.3):仅"前后端要对齐 / 错一字即 bug"的字符串进这里。
一次性展示文案直接写在前端组件 JSX,不进常量。

与 `frontend/src/config/country-registration-rules.ts` **逐字一致**(手工同步)。
"""
from __future__ import annotations

import re

# 9 国 ISO 2 位 code(用于 schema 枚举校验)
COUNTRY_CODES: tuple[str, ...] = (
    "CN",
    "KH",
    "PK",
    "MA",
    "IQ",
    "ID",
    "MY",
    "SA",
    "AE",
)

# 国家元数据(后端目前只用到 local_lang 与 name_*,精确正则放前端)
COUNTRY_META: dict[str, dict[str, str]] = {
    "CN": {"name_zh": "中国", "name_en": "China", "local_lang": "zh",
           "reg_no_hint": "统一社会信用代码 18 位"},
    "KH": {"name_zh": "柬埔寨", "name_en": "Cambodia", "local_lang": "km",
           "reg_no_hint": "MOC 注册号 6-12 位数字"},
    "PK": {"name_zh": "巴基斯坦", "name_en": "Pakistan", "local_lang": "ur",
           "reg_no_hint": "SECP 注册号 7-10 位字母数字"},
    "MA": {"name_zh": "摩洛哥", "name_en": "Morocco", "local_lang": "ar",
           "reg_no_hint": "ICE 企业统一编号 15 位数字"},
    "IQ": {"name_zh": "伊拉克", "name_en": "Iraq", "local_lang": "ar",
           "reg_no_hint": "MoC 商业登记号 6-10 位数字"},
    "ID": {"name_zh": "印尼", "name_en": "Indonesia", "local_lang": "id",
           "reg_no_hint": "NIB 注册号 13 位数字"},
    "MY": {"name_zh": "马来西亚", "name_en": "Malaysia", "local_lang": "ms",
           "reg_no_hint": "SSM 注册号 12 位数字"},
    "SA": {"name_zh": "沙特阿拉伯", "name_en": "Saudi Arabia", "local_lang": "ar",
           "reg_no_hint": "CR 商业登记号 10 位数字"},
    "AE": {"name_zh": "阿联酋", "name_en": "UAE", "local_lang": "ar",
           "reg_no_hint": "Trade License No 6-12 位字母数字"},
}

# language_preference 合法值:BCP 47 locale tag 封闭白名单(10 个)
# 与前端 LANGUAGE_CODES 必须逐字一致
LANGUAGE_CODES: tuple[str, ...] = (
    "zh-CN", "en", "km-KH", "ur-PK", "ar-MA", "ar-IQ", "ar-SA", "ar-AE", "id-ID", "ms-MY", "sw-TZ",
)

# 后端长度兜底(所有国家)
REGISTRATION_NO_MAX_LENGTH = 50

# 各国注册号精确正则(后端兜底校验,与 frontend/src/config/country-registration-rules.ts 逐字对齐)
REGISTRATION_NO_PATTERNS: dict[str, "re.Pattern[str]"] = {
    "CN": re.compile(r"^[0-9A-Z]{18}$"),    # 统一社会信用代码 18 位
    "KH": re.compile(r"^[0-9]{6,12}$"),     # MOC 注册号 6-12 位数字
    "PK": re.compile(r"^[A-Z0-9]{7,10}$"),  # SECP 注册号 7-10 位字母数字
    "MA": re.compile(r"^[0-9]{15}$"),       # ICE 企业统一编号 15 位数字
    "IQ": re.compile(r"^[0-9]{6,10}$"),     # MoC 商业登记号 6-10 位数字
    "ID": re.compile(r"^[0-9]{13}$"),       # NIB 营业识别号 13 位纯数字
    "MY": re.compile(r"^[0-9]{12}$"),       # SSM 注册号 12 位纯数字
    "SA": re.compile(r"^[0-9]{10}$"),       # CR 商业登记号 10 位数字
    "AE": re.compile(r"^[A-Z0-9]{6,12}$"),  # Trade License No 6-12 位字母数字
}


def validate_registration_no(country_code: str, registration_no: str) -> bool:
    """按国别精确校验注册号格式;未配置正则的国家只走 schema 长度兜底,返回 True。

    前端校验可被绕过(直接调 API),后端在此兜底,保证 (country, regno) 格式一致。
    """
    pattern = REGISTRATION_NO_PATTERNS.get(country_code)
    return True if pattern is None else bool(pattern.match(registration_no))

# 重复注册错误文案(前后端逐字一致,不暴露 owner / 公司名信息)
DUPLICATE_REGISTRATION_ERROR_MESSAGE = (
    "当前企业已在平台注册。如需加入,请联系您所在企业的平台管理员添加账号。"
)

# v1.5 Δ2:邮箱 / 手机号全局唯一,前后端按数字 code 识别(严禁字符串比较)
BUSINESS_CODE_SUPPLIER_ALREADY_REGISTERED = 40901
BUSINESS_CODE_EMAIL_ALREADY_REGISTERED = 40902
BUSINESS_CODE_PHONE_ALREADY_REGISTERED = 40903

EMAIL_ALREADY_REGISTERED_MESSAGE = "该邮箱已注册,请直接登录或更换邮箱"
PHONE_ALREADY_REGISTERED_MESSAGE = "该手机号已注册,请直接登录或更换手机号"

# v1.5 Δ3:多错误并发时顶部 banner 文案(单错误时不使用)
MULTIPLE_VALIDATION_ERRORS_MESSAGE = "请修正以下问题"

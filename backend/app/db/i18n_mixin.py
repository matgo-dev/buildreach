"""i18n Mixin — 为需要多语言的业务表提供 source_lang + trans_meta 字段。

用法:
    class Product(Base, TimestampUpdateMixin, I18nMixin):
        __tablename__ = "products"
        id: Mapped[int] = mapped_column(primary_key=True)
        name_zh: Mapped[str | None] = mapped_column(String(200))
        name_en: Mapped[str | None] = mapped_column(String(200))

    # 创建时由 i18n_write.apply_i18n_create 设置 source_lang 和 trans_meta
    # 编辑时由 i18n_write.apply_i18n_edit 维护翻译状态

trans_meta 结构:
    {
        "name_zh": "src",       # 源语言标记
        "name_en": "auto",      # 机器翻译
        "desc_zh": "src",
        "desc_en": "manual",    # 人工编辑过
    }

状态枚举:
    src     — 源语言原文(仅 source_lang 列可持有)
    manual  — 人工填写/编辑
    stale   — 源语言已变更,此翻译待刷新(不覆盖人工编辑值)
    auto    — 机器翻译(当前 mock)
    pending — 翻译请求已发出,结果未回
    failed  — 翻译失败,待补偿重试

金额字段约定(不在本 mixin,记录在此供参考):
    - 金额字段旁必须有 currency VARCHAR(3) 列,值为 ISO 4217 货币代码(USD/KES/CNY)
    - 时间统一通过 TimestampMixin / TimestampUpdateMixin 的 UTC 方案
"""
from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column


class I18nMixin:
    """业务表 i18n 基础字段。source_lang 创建后不可变,trans_meta 仅由 i18n_write 维护。"""

    # 创建时从用户 language_preference 写入,之后不可变
    source_lang: Mapped[str] = mapped_column(
        String(10), nullable=False, default="zh",
    )

    # 翻译状态元数据,key 格式 "{field}_{locale}",value 为状态字符串
    trans_meta: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}",
    )

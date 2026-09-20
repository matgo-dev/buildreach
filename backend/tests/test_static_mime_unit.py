"""register_extra_mime_types 的纯逻辑测试:在"MIME 表不认识 webp"的环境下注册后能正确识别。"""
from __future__ import annotations

import mimetypes

from app.core.mime import register_extra_mime_types


def test_webp_registered_even_when_table_lacks_it():
    mimetypes.init(files=[])  # 只剩 Python 内置默认表(不读系统 /etc/mime.types)
    # 模拟 slim 容器 / Python 3.12 及以前:内置表里也没有 webp
    for table in (mimetypes.types_map, mimetypes.common_types):
        table.pop(".webp", None)
    mimetypes.inited = True
    try:
        assert mimetypes.guess_type("x_thumb.webp")[0] != "image/webp"
        register_extra_mime_types()
        assert mimetypes.guess_type("x_thumb.webp")[0] == "image/webp"
    finally:
        mimetypes.init()  # 还原全局表
        register_extra_mime_types()

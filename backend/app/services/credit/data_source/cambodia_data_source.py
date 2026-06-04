"""柬埔寨数据源(Δ7 Step 8)。

fetch_xxx 从数据库读最新一条快照(与 MockDataSource 模式一致);抓取由异步任务
(harvest_task)驱动,与 fetch_xxx 解耦。

本期读取逻辑与 MockDataSource 完全一致,故直接继承复用;独立成类是为了:
1. registry 按 country_code='KH' 路由
2. 未来定制(如"按 harvest_run_id 优先级排序取数")时只改这里,不动 MockDataSource
"""
from __future__ import annotations

from app.services.credit.data_source.mock_data_source import MockDataSource


class CambodiaDataSource(MockDataSource):
    """柬埔寨数据源。本期与 MockDataSource 同为"读最新一条快照"。"""

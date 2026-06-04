"""数据源抽象 + 实现(信用评估 §3.1)。

第一阶段:`MockDataSource` 直接从 credit_company_*_data 表读 seed 数据。
后续(TODO T-2):新增 `QichachaDataSource` 等真实数据源,通过 registry 按国别路由。
"""
from app.services.credit.data_source.base import DataSource
from app.services.credit.data_source.mock_data_source import MockDataSource
from app.services.credit.data_source.registry import resolve_data_source

__all__ = ["DataSource", "MockDataSource", "resolve_data_source"]

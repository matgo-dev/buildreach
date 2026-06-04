"""Cambodia 去 mock 占位评分 — 清理存量 KH mock 数据(Δ8)

Revision ID: 20260526_0009
Revises: 20260525_0008
Create Date: 2026-05-26

[allow-destructive-migration]

背景:Δ8 起柬埔寨注册不再写 mock 占位评分(仅真实 harvest 数据)。
存量的 KH mock 数据需清除,避免列表/详情展示残留假数据。

如何区分 mock 与真实(关键):
- mock 占位 snapshot 的 trigger_type = 'INITIAL'(registration_hook 写);
  真实 harvest snapshot 的 trigger_type = 'REAL_TIME_ONBOARD' / 'MANUAL_RECALC'。
  故按 trigger_type='INITIAL' 精确锁定 mock,不误删真实评分。
- 4 张数据表的 mock 行 data_source = 'mock'(DataSourceTag.MOCK,小写);
  真实行是 official/api/public/media/missing。

清理顺序(子→父,FK 无 cascade 必须手动按序):
1. score_audit_log:先把"真实快照的 audit 行 previous 指向 mock"置 NULL(保住真实 audit 链),
   再删 current 指向 mock 的 audit 行
2. score_detail:删 mock snapshot 的明细
3. score_snapshot:删 KH INITIAL(mock)快照
4. credit_company_*_data ×4:删 KH 公司下 data_source='mock' 的行

down 不可逆(mock 数据本就是生成的,无业务价值)。
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260526_0009"
down_revision: Union[str, None] = "20260525_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# KH 公司下的 mock 占位快照 id 集合(子查询复用)
_KH_MOCK_SNAPSHOTS = """
    SELECT s.id FROM score_snapshot s
    JOIN credit_company c ON c.id = s.company_id
    WHERE c.country_code = 'KH' AND s.trigger_type = 'INITIAL'
"""

_MOCK_DATA_TABLES = (
    "credit_company_basic_data",
    "credit_company_finance_data",
    "credit_company_legal_data",
    "credit_company_certification",
)


def upgrade() -> None:
    # 1. 解除真实 audit 行对 mock 快照的 previous 引用(保住真实评分的审计链)
    op.execute(f"""
        UPDATE score_audit_log SET previous_snapshot_id = NULL
        WHERE previous_snapshot_id IN ({_KH_MOCK_SNAPSHOTS});
    """)
    # 删 current 指向 mock 快照的 audit 行(这类行本身就是 mock 评分产生的)
    op.execute(f"""
        DELETE FROM score_audit_log
        WHERE current_snapshot_id IN ({_KH_MOCK_SNAPSHOTS});
    """)

    # 2. score_detail
    op.execute(f"""
        DELETE FROM score_detail
        WHERE snapshot_id IN ({_KH_MOCK_SNAPSHOTS});
    """)

    # 3. score_snapshot(mock 占位)
    op.execute(f"""
        DELETE FROM score_snapshot
        WHERE id IN ({_KH_MOCK_SNAPSHOTS});
    """)

    # 4. 4 张数据表的 mock 行
    for tbl in _MOCK_DATA_TABLES:
        op.execute(f"""
            DELETE FROM {tbl}
            WHERE data_source = 'mock'
              AND company_id IN (SELECT id FROM credit_company WHERE country_code = 'KH');
        """)


def downgrade() -> None:
    # 不可逆:mock 数据无业务价值,不恢复
    pass

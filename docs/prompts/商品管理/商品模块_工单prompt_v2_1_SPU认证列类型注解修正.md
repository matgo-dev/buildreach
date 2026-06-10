# 商品模块 v2.1 工单 prompt — SPU certifications 类型注解修正

> 基线：main（含迁移 `f2e83cdfe399`，rfqs 认证/附件列已为 JSON）
> 对象：`products` 表 `certifications` 列（类型注解，非 DB 变更）
> 性质：纯 Python 类型标注修正，无 alembic 迁移
> 仓库位置：`docs/prompts/商品管理/`
> 规范依据：与 `rfqs.required_certifications`（`Mapped[list | None]`）对齐

## 背景

`products.certifications` 列在 DB 中已经是 `JSON` 类型，`default=list`，schema 层也全部以 `list | None` 读写。但模型类型注解错写为 `Mapped[dict | None]`，与实际语义（认证码列表，如 `["ISO9001", "CE"]`）不符。

对比：

| 模型 | 当前注解 | DB 类型 | default | Schema 层 | 实际语义 |
|---|---|---|---|---|---|
| `Product` (SPU) | `Mapped[dict \| None]` ❌ | JSON | `list` | `list \| None` | 认证码列表 |
| `Rfq` | `Mapped[list \| None]` ✅ | JSON | `list` | `list[str]` | 认证码列表 |

## 改动

1. `backend/app/db/models/product.py` 第 81 行：

```python
# 改前
certifications: Mapped[dict | None] = mapped_column(JSON, default=list)

# 改后
certifications: Mapped[list | None] = mapped_column(JSON, default=list)
```

2. 无 alembic 迁移（DB 列类型已正确，仅修正 Python 类型注解）。
3. 无 schema 变更（schema 层已经是 `list | None`）。

## 验收

- `Product.certifications` 类型注解为 `Mapped[list | None]`。
- 无新增 alembic 迁移文件。
- `pytest` 全量通过，无回归。

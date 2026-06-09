# 全平台软删除改造 v0.1 工单 prompt — SoftDeleteMixin 引入与业务代码改造

> 基线：main（含 v1.6「聚合保存 SKU 归属校验」/ #33、#35 安全加固、#36 dev.sh）
> 性质：基础设施 + 业务改造，后端为主，前端联动
> 仓库位置：`docs/prompts/`
> 关联 issue：#38
> 规范依据：CLAUDE.md「删除约定（强制）」章节

---

## 一、本质

当前全平台所有删除操作都是硬删（`db.delete()` / `sa_delete()`），业务数据删了就没了。B2B 场景下订单/询价会引用商品、SKU、图片，硬删导致 FK 断链、审计不可追溯。

核心原则：**业务记录软删，文件资源延迟清理**。两套机制，不混为一谈。

---

## 二、现状（已核实）

以下位置存在硬删：

| 文件 | 行为 | 实体 |
|---|---|---|
| `app/services/product.py:382` | `db.delete(product)` | SPU |
| `app/services/product.py:663` | `db.delete(sku)` | SKU |
| `app/services/product.py:1252` | `db.delete(sku)` | SKU（聚合保存中） |
| `app/services/product.py:1008` | `db.delete(img)` | 商品图片记录 |
| `app/services/product.py:835` | `db.delete(ps)` | 供应商关系 |
| `app/services/product.py:239,607,1207,1392` | `sa_delete(ProductAttr)` | 商品属性 |
| `app/services/product.py:762` | `sa_delete(SkuPriceTier)` | 价格梯度 |
| `app/api/v1/credit.py:607` | `db.delete(row)` | 信用数据 |
| `app/rbac/sync.py:112,191` | `db.delete(...)` | 权限/角色权限关联 |

所有模型均无 `deleted_at` / `deleted_by` 字段。

---

## 三、设计

### 3.1 SoftDeleteMixin

新建 `app/db/soft_delete_mixin.py`：

```python
class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None, index=True
    )
    deleted_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, default=None
    )
```

- `deleted_at` 加索引，查询过滤高频使用
- `deleted_at IS NULL` = 未删除，有值 = 已删除

### 3.2 接入范围

**当前有删除操作的表**接入 `SoftDeleteMixin`，没有删除功能的表等后续做到再加：

| 模型 | 说明 | 当前硬删位置 |
|---|---|---|
| `Product` | SPU | `product.py:382` |
| `ProductSku` | SKU | `product.py:663,1252` |
| `ProductImage` | 商品图片记录 | `product.py:1008` |
| `ProductAttr` | 商品属性 | `product.py:239,607,1207,1392` |
| `SkuPriceTier` | 阶梯价 | `product.py:762` |
| `ProductSupplier` | 供货关系 | `product.py:835` |
| `CreditCompany` 相关 | 信用数据 | `credit.py:607` |
| `Permission` | 权限 | `rbac/sync.py:112` |
| `RolePermission` | 角色权限关联 | `rbac/sync.py:191` |

**暂不接入**（当前无删除功能，后续模块开发时按需加入）：
- User / Role / UserRole
- BuyerOrganization / SupplierOrganization / BuyerMember / SupplierMember
- Category / AttrTemplate
- AuditLog / TranslationGlossary
- 其余 credit_* 系列表（除上述有硬删的）

### 3.3 查询过滤

Service 层提供统一工具方法：

```python
def not_deleted(query, model):
    """给查询追加 deleted_at IS NULL 过滤"""
    return query.where(model.deleted_at.is_(None))
```

**规则**：
- Buyer API：必须过滤，无例外
- Operator API：默认过滤；后续可加「已删除」筛选视图（本单不做 UI）
- Admin API：默认过滤
- 审计/恢复场景：单独走不过滤的查询方法

**逐文件检查**：改造时须逐个 `select()` / `query()` 确认是否已加过滤，不能遗漏。

### 3.4 删除操作改造

**通用模式**：

```python
# 之前
await db.delete(obj)

# 之后
obj.deleted_at = _utcnow()
obj.deleted_by = current_user.id
```

**批量软删（替代 sa_delete）**：

```python
# 之前
await db.execute(sa_delete(ProductAttr).where(ProductAttr.sku_id == sku_id))

# 之后
await db.execute(
    update(ProductAttr)
    .where(ProductAttr.sku_id == sku_id, ProductAttr.deleted_at.is_(None))
    .values(deleted_at=_utcnow(), deleted_by=current_user.id)
)
```

### 3.5 级联软删

删 SPU 时必须同步软删所有子实体：

```
delete_product(product_id, current_user)
  ├─ product.deleted_at = now()
  ├─ UPDATE product_skus SET deleted_at=now(), deleted_by=uid WHERE product_id=X AND deleted_at IS NULL
  ├─ UPDATE product_images SET deleted_at=now(), deleted_by=uid WHERE product_id=X AND deleted_at IS NULL
  ├─ UPDATE product_attrs SET deleted_at=now(), deleted_by=uid WHERE product_id=X AND deleted_at IS NULL
  ├─ UPDATE sku_price_tiers SET deleted_at=now(), deleted_by=uid WHERE sku_id IN (...) AND deleted_at IS NULL
  └─ UPDATE product_suppliers SET deleted_at=now(), deleted_by=uid WHERE sku_id IN (...) AND deleted_at IS NULL
```

删 SKU 同理，级联软删其下属性、价格梯度、供应商关系。

### 3.6 业务规则

- `ACTIVE` 商品必须先下架再删除，直接删除返回错误
- SKU 全部软删后，若 SPU 无任何 ACTIVE 且未删除 SKU，SPU 自动下架
- 已软删记录不可上架、不可编辑、不可参与新业务
- 聚合保存中的 SKU 删除逻辑同样改为软删

### 3.7 Partial Unique Index

带唯一约束的字段改为 partial unique index，允许软删后重建同名记录：

```python
# Alembic migration 示例
op.create_index(
    "uq_product_skus_sku_code_active",
    "product_skus",
    ["sku_code"],
    unique=True,
    postgresql_where=text("deleted_at IS NULL"),
)
```

检查所有现有唯一约束，逐个改造。

### 3.8 图片文件延迟清理（本单只做 DB 软删，文件清理留占位）

本单范围：
- 图片删除接口改为软删 DB 记录（`product_images.deleted_at = now()`）
- 前台/后台查询默认不再展示已软删图片
- **不在请求链路中删除文件**

文件物理清理（后续单独工单）：
- 定时任务扫描 `deleted_at` 超过保留期的图片记录
- 保留期：替换/删除图片 30 天，软删商品下图片 90 天，被单据快照引用的不清理
- 确认无活跃引用后物理删除文件，失败记日志下次重试
- 代码中留 `TODO: 图片文件延迟清理任务待实现`

### 3.9 单据快照（设计预留，本单不实现）

订单/询价生成时应快照：商品名、SKU 名、规格、价格、主图 URL。本单在 CLAUDE.md 已写入规范，代码不动，后续订单模块实现时落地。

---

## 四、任务拆解

### T1 新建 SoftDeleteMixin + Alembic migration

- 新建 `app/db/soft_delete_mixin.py`
- 所有模型类接入 `SoftDeleteMixin`
- 生成 Alembic migration：全表加 `deleted_at` + `deleted_by` 字段
- 现有唯一约束改为 partial unique index（`WHERE deleted_at IS NULL`）

### T2 Service 层查询过滤

- 提供 `not_deleted()` 工具方法
- 逐文件检查所有 `select()` / `query()`，加 `deleted_at IS NULL` 过滤
- 覆盖范围：product service、credit service、rbac sync、所有 API 端点中的内联查询

### T3 商品模块删除操作改造

- `delete_product` → 级联软删 SPU + 所有子实体
- `delete_sku` → 软删 SKU + 级联子实体；全部 SKU 软删后 SPU 自动下架
- `delete_product_image` → 软删图片记录（不删文件）
- `delete_supplier_relation`（`db.delete(ps)`）→ 软删
- 聚合保存中的 SKU 删除 → 软删
- 属性全量替换中的 `sa_delete(ProductAttr)` → 批量软删
- 价格梯度替换中的 `sa_delete(SkuPriceTier)` → 批量软删
- `ACTIVE` 商品删除前置校验：必须先下架

### T4 信用模块删除操作改造

- `credit.py:607` 的 `db.delete(row)` → 软删

### T5 RBAC 同步删除操作改造

- `rbac/sync.py:112,191` 的 `db.delete(...)` → 软删
- 权限同步清理过期配置改为标记 `deleted_at`

### T6 测试

- 现有 product 相关测试适配软删改造
- 新增测试用例：
  - 软删后常规查询不返回已删记录
  - 级联软删：删 SPU 后子实体均被标记
  - 已软删记录不可编辑/上架
  - SKU 全部软删后 SPU 自动下架
  - Partial unique index：软删后可重建同名 SKU code
  - 批量软删（属性/价格梯度替换场景）

---

## 五、RBAC

不新增权限点。删除操作沿用现有权限（`product:delete` 等）。

---

## 六、i18n

无新增前端文案。删除确认弹窗文案已有，行为从硬删改为软删对用户透明。

---

## 七、不做的事（明确排除）

- ❌ 图片文件物理清理定时任务（单独工单）
- ❌ Operator「已删除」筛选视图 UI（后续需求）
- ❌ 恢复（反删除）功能及 UI
- ❌ 单据快照实现（订单模块时落地）
- ❌ 前端删除交互变更（行为对用户透明，弹窗确认不变）

---

## 八、验收

- 删除 SPU → DB 记录 `deleted_at` 有值，子实体同步标记，列表/详情不再展示
- 删除 SKU → 同上；最后一个 SKU 删除后 SPU 自动下架
- 删除图片 → DB 记录标记，文件仍在（不删文件）
- 所有列表/详情 API 不返回已软删记录
- `ACTIVE` 商品直接删除 → 400 错误，提示先下架
- 软删同名 SKU code 后可重新创建
- 已软删记录不可编辑、不可上架
- RBAC 同步清理后，过期权限标记 `deleted_at` 而非物理删除
- 现有测试全部通过 + 新增软删测试通过

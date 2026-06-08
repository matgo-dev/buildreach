# v1.4 复合保存工单 — Code Review 补丁

> 来源：基于 `feat/product-aggregate-save` 分支的代码审阅，非原始工单范围，实施时一并修复。
> 日期：2026-06-08

---

## 额外修复项

### [P0] 运营 API 叠加 OPERATOR 角色守卫

**现象**：`operator_products.py` 只校验权限点（`product:read/write`），但 BUYER 持有 `PRODUCT_READ`、SUPPLIER 持有 `PRODUCT_READ/WRITE`，可直接调用运营接口拿到供应商成本。

**修复**：router 级 `dependencies=[Depends(require_any_role("OPERATOR"))]`，所有运营端点强制 OPERATOR 角色。

**文件**：`backend/app/api/v1/operator_products.py`

---

### [P1] 创建接口移除 status 字段，强制 DRAFT

**现象**：`ProductCreate` schema 暴露 `status` 字段，旧 `POST /operator/products` 可直接创建 ACTIVE 商品，绕过上架校验。

**修复**：`ProductCreate` 移除 `status`，`create_product` service 强制 `ProductStatus.DRAFT`。

**文件**：`backend/app/schemas/product.py`、`backend/app/services/product.py`

---

### [P1] SKU status 从编辑 schema 移除，新增独立动作端点

**现象**：`SkuUpdate` / `AggregateSkuCreate` / `AggregateSkuSave` 含 `status` 字段，普通编辑可直接改 SKU 状态，违反状态机规则。

**修复**：
- 三个 schema 移除 `status`，新建 SKU 强制 `SkuStatus.ACTIVE`
- 新增 `SkuStatusUpdate` schema + `update_sku_status` service
- 新增 `PATCH /operator/products/{product_id}/skus/{sku_id}/status` 端点
- 前端 `operatorProductsApi.updateSkuStatus()` 对应

**文件**：schema / service / route / 前端 API client

---

### [P1] force=true 上架校验跳过 — 保持现状

**决策**：前后端均保留 `force=true` 跳过上架校验，供当前阶段快速测试用。后续正式上线前统一收口。

---

### [P2] 创建页发布失败跳转草稿详情

**现象**：聚合创建成功但图片上传或发布失败时，商品已落库为草稿，但前端只显示错误，用户无法恢复。

**修复**：失败时提示"商品已保存为草稿"，显示"进入详情"按钮跳转到详情页继续编辑。

**文件**：`frontend/.../create/_components/ProductCreatePage.tsx`

---

### [P2] 供货关系上架策略 TODO

**决策**：当前允许无供货关系上架。在 `update_product_status` 发布校验处标注 TODO，后续需决策是否强制。

**文件**：`backend/app/services/product.py`

---

## 聚合保存实施中发现并修复的 bug

### skus=None 误删全部 SKU

**现象**：`PUT /aggregate` 只传 `name` 不传 `skus` 时，所有 SKU 被 diff 删除。

**根因**：`data.skus` 为 `None`（未传）时 `(data.skus or [])` 变空列表，diff 认为"期望 0 个 SKU"。

**修复**：区分 `skus=None`（不修改 SKU）和 `skus=[]`（显式清空）。`None` 时跳过 diff。

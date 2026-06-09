# Prompt: unit / currency 从 SKU 提升到 SPU

## 背景

当前 `unit`（计量单位）和 `currency`（币种）挂在 SKU 表上，但业务上同一商品所有 SKU 共享同一单位和币种。这是数据模型 bug——允许同一商品下不同 SKU 选不同单位/币种，实际不应该发生。需要将这两个字段提升到 SPU（Product）表。

线上无真实数据，部署后 `reset_db.sh` 重置即可，不需要写数据搬迁 SQL。

## 前置条件

在执行本任务前，确保以下改动已合并到 main：
- SKU 创建页基础信息字段补齐（name/material/manufacturer_model/color + ComboInput）
- 如果尚未合并，先切分支提交合并后再开始本任务

## 改动范围

### 1. 数据库模型

**`backend/app/db/models/product.py`** — Product 模型加两列：
```python
unit: Mapped[str] = mapped_column(String(20), nullable=False, default="PCS")
currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TZS")
```
放在 `hs_code` 和 `certifications` 之间。

**`backend/app/db/models/product_sku.py`** — ProductSku 模型删两列：
- 删 `currency`（当前第 67 行）
- 删 `unit`（当前第 68 行）

### 2. Alembic 迁移

生成迁移：`alembic revision --autogenerate -m "move unit currency from sku to spu"`

迁移内容应包含：
- `products` 表加 `unit VARCHAR(20) NOT NULL DEFAULT 'PCS'`
- `products` 表加 `currency VARCHAR(3) NOT NULL DEFAULT 'TZS'`
- `product_skus` 表删 `unit` 列
- `product_skus` 表删 `currency` 列

不需要数据搬迁 SQL（线上无真实数据）。

### 3. 后端 Schema (`backend/app/schemas/product.py`)

**SPU Schema 加字段：**
- `ProductCreate`：加 `unit: SkuUnitCode = "PCS"` 和 `currency: str = "TZS"`
- `ProductUpdate`：加 `unit: SkuUnitCode | None = None` 和 `currency: str | None = None`
- `ProductPublic`：`unit` 和 `currency` 改为从 SPU 直接读取（去掉原来从默认 SKU 取的逻辑）
- `ProductOperator` / `ProductOperatorDetail`：同上
- `ProductAggregateCreate`：加 `unit` 和 `currency`

**SKU Schema 删字段：**
- `SkuCreate`：删 `unit` 和 `currency`
- `SkuUpdate`：删 `unit` 和 `currency`
- `AggregateSkuCreate`：删 `unit` 和 `currency`
- `SkuPublic`：删 `unit` 和 `currency`
- `SkuOperator`：删 `unit` 和 `currency`

### 4. 后端 Service (`backend/app/services/product.py`)

- `create_product()`：处理 SPU 的 unit/currency 写入
- `update_product()`：处理 SPU 的 unit/currency 更新
- `_create_sku_in_aggregate()`：删除 unit/currency 赋值
- `_update_sku_in_aggregate()`：从 plain_fields 元组中删除 unit/currency
- `spu_price_range()`：currency 改从 SPU 模型读取，不再从 SKU 取
- `default_sku_fields()`：unit 改从 SPU 模型读取，不再从默认 SKU 取

### 5. 后端 API

**`backend/app/api/v1/operator_products.py`：**
- `_sku_to_operator()` 序列化函数：删 currency/unit 字段
- 聚合创建端点：unit/currency 从 SPU payload 读取

**`backend/app/api/v1/products.py`：**
- 公开 API 序列化：unit/currency 改从 SPU 模型读取

### 6. 前端 API 层 (`frontend/src/lib/api/operatorProducts.ts`)

- `SkuCreateInput`：删 `unit` 和 `currency`
- `SkuUpdateInput`：删 `unit` 和 `currency`
- `AggregateSkuInput`：删 `unit` 和 `currency`
- `ProductAggregateCreateInput`：加 `unit: SkuUnitCode` 和 `currency?: string`

### 7. 前端创建页

**`ProductCreatePage.tsx`：**
- `SkuFormState` 接口：删 `unit` 和 `currency`
- `createEmptySku()`：删 unit/currency 默认值
- `SpuFormState` 接口：加 `unit: SkuUnitCode` 和 `currency: string`
- `INITIAL_SPU`：加 `unit: "PCS"` 和 `currency: "TZS"`
- SPU 表单区（section-basic）：加 unit 下拉选择器和 currency 下拉选择器
- `handleSubmit` payload 组装：unit/currency 从 SPU 级传入，SKU 不再传

**`SkuCard.tsx`：**
- 删除 unit 下拉选择器（原商务参数区第一个字段）
- 删除 currency 下拉选择器
- 价格标签中的 `({sku.currency})` 改为从 props 传入的 SPU currency

### 8. 前端编辑页

**`ProductDetailPage.tsx`：**
- unit/currency 展示改从 SPU 级数据读取
- 编辑态的 unit/currency 移到 SPU 基本信息编辑区

**`SkuEditModal.tsx`：**
- 删除 unit 和 currency 输入框
- `SkuFormData` 接口删 unit 和 currency

### 9. 前端买家页

**`mall/products/[id]/page.tsx`：**
- `selectedSku.unit` → 改从商品级数据读取（API 响应结构变了）
- `selectedSku.currency` → 同上

**`components/mall/ProductCard.tsx`：**
- `product.unit` 位置不变（ProductPublic 已改为从 SPU 读）

**`components/mall/PriceTiers.tsx`：**
- unit 从 props 透传，组件内部不变

### 10. 阶梯价处理

**`backend/app/db/models/sku_price_tier.py`：**
- `currency` 列保留（阶梯价仍需记录币种，与 SPU 的 currency 保持一致）
- Service 层 `_replace_price_tiers()` 中 currency 改从 SPU 取

## 验证清单

### 后端
- [ ] `alembic upgrade head` 无报错
- [ ] `pytest` 全量通过
- [ ] `POST /operator/products/aggregate` — unit/currency 在 SPU 级传入，SKU 不传
- [ ] `GET /api/v1/products/{id}` — unit/currency 从 SPU 返回
- [ ] SKU 响应中不再包含 unit/currency

### 前端
- [ ] `pnpm build` 无报错
- [ ] 创建商品页：unit/currency 在 SPU 基本信息区选择，SKU 卡片无这两个字段
- [ ] 编辑页：unit/currency 在 SPU 基本信息区编辑
- [ ] 买家详情页：unit 和价格展示正常
- [ ] 商城列表页：卡片上 unit 展示正常

### 部署
- commit message 需加 `[allow-destructive-migration]`（含 drop_column）
- 或手动 SSH 执行 `bash deploy/deploy.sh`
- ECS 部署后执行 `reset_db.sh` 重置数据库 + 重新 seed 品类

# 买方询价篮 + 提交询价 — 前端实现工单

> 后端 API 已就绪（cart + rfq），本工单覆盖买方侧前端全部页面。

---

## 0. 实现顺序

| 步骤 | 交付物 | 依赖 |
|------|--------|------|
| ① | `lib/api/cart.ts` + `lib/api/rfqs.ts` + TS 类型 | 无 |
| ② | `stores/cartStore.ts` | ① |
| ③ | 商品详情页改造（加购按钮 + 角标） | ①② |
| ④ | 询价篮页面 `/buyer/cart` | ①②③ |
| ⑤ | 询价表单页 `/buyer/rfqs/create` | ①④ |
| ⑥ | 询价列表 `/buyer/rfqs` + 详情 `/buyer/rfqs/[id]` | ① |
| 每步 | 同步补 `messages/zh.json` + `messages/en.json` | — |

---

## ① API 客户端 + 类型

### `lib/api/cart.ts`

后端接口契约（全部返回 `{ code, message, data }`，以下只列 `data` 部分）：

| 方法 | 路径 | 请求体 | data 类型 |
|------|------|--------|-----------|
| GET | `/api/v1/cart` | — | `CartPublic` |
| POST | `/api/v1/cart/items` | `{ sku_id: number, quantity: number }` | `CartPublic` |
| PATCH | `/api/v1/cart/items/{item_id}` | `{ quantity: number }` | `CartPublic` |
| DELETE | `/api/v1/cart/items/{item_id}` | — | `CartPublic` |
| DELETE | `/api/v1/cart/items` | — | `CartPublic` |

```typescript
// 类型定义
interface CartItemPublic {
  item_id: number
  sku_id: number
  product_id: number
  quantity: number          // Decimal(18,3)
  sku_code: string
  sku_name: string | null
  product_name: string | null
  manufacturer_model: string | null
  color: string | null
  material: string | null
  unit: string | null
  moq: number | null
  is_purchasable: boolean
  unavailable_reason: string | null  // SKU_DELETED | SKU_INACTIVE | PRODUCT_DELETED | PRODUCT_INACTIVE
  main_image: string | null
}

interface CartPublic {
  id: number | null
  items: CartItemPublic[]
}
```

### `lib/api/rfqs.ts`

| 方法 | 路径 | 请求体 | data 类型 |
|------|------|--------|-----------|
| POST | `/api/v1/rfqs` | `RfqCreate` | `RfqBuyerPublic` |
| GET | `/api/v1/rfqs` | query: page/page_size/status/mine | `RfqListResponse` |
| GET | `/api/v1/rfqs/{rfq_id}` | — | `RfqBuyerPublic` |
| PATCH | `/api/v1/rfqs/{rfq_id}/cancel` | `{ cancel_reason?: string }` | `RfqBuyerPublic` |

```typescript
// 请求
type SourceType = "CART" | "DIRECT"

interface RfqDirectItem {
  sku_id: number
  quantity: number
  target_unit_price?: number   // Decimal(18,4), >= 0
  remark?: string
}

interface RfqCreate {
  source_type: SourceType
  cart_item_ids?: number[]      // CART 模式
  items?: RfqDirectItem[]       // DIRECT 模式（本期只实现 CART 路径，BUYER DIRECT 留 TODO；后端已支持）
  contact_name?: string
  contact_phone?: string
  contact_email?: string
  requested_delivery_place?: string
  expected_delivery_date?: string  // 前端提交 UTC ISO datetime: "YYYY-MM-DDT00:00:00Z"
  target_currency?: string         // ISO 4217, 如 USD/KES
  required_certifications?: string[]
  attachment_urls?: string[]
  remark?: string
}

// 响应
interface RfqItemPublic {
  id: number
  sku_id: number
  product_name_snapshot: string | null
  sku_spec_snapshot: string | null
  uom_snapshot: string | null
  quantity: number
  target_unit_price: number | null
  remark: string | null
}

interface RfqBuyerPublic {
  id: number
  rfq_no: string
  status: string    // DRAFT | SUBMITTED | QUOTED | ACCEPTED | REJECTED | EXPIRED | CANCELLED
  source: string    // BUYER_SELF | OPERATOR_PROXY
  contact_name: string | null
  contact_phone: string | null
  contact_email: string | null
  remark: string | null
  requested_delivery_place: string | null
  expected_delivery_date: string | null
  target_currency: string | null
  required_certifications: string[] | null
  attachment_urls: string[] | null
  created_at: string | null
  updated_at: string | null
  items: RfqItemPublic[]
  // quote 字段：报价回填后端合并后再加，本期不定义
}

interface RfqListResponse {
  items: RfqBuyerPublic[]
  total: number
  page: number
  page_size: number
}
```

---

## ② cartStore（Zustand）

```typescript
interface CartState {
  count: number           // 角标数字（可购商品数）
  refreshFlag: number     // 自增触发 SWR revalidate
  setCount: (n: number) => void
  syncFromCart: (cart: CartPublic) => void  // 从返回的 CartPublic 直接算 count
  triggerRefresh: () => void
}
```

**count 更新链路（全局闭环）**：
- `syncFromCart(cart)`：从 `CartPublic` 算出 `items.filter(i => i.is_purchasable).length` 写入 count。**count 语义是"可购 SKU 行数"，不是 quantity 总和。** 所有返回 CartPublic 的接口（加购/改量/删除/清空/GET）调用后都用此方法更新。
- 登录后首次初始化：由 Buyer layout（或 AuthProvider ready 回调）触发一次 `GET /cart`，调 `syncFromCart` 写入初始 count。
- `triggerRefresh()`：自增 flag，询价篮页面 SWR 监听此 flag 做 revalidate。
- 提交询价成功后：后端自动清对应 cart items，前端调 `GET /cart` → `syncFromCart` 更新角标。
- Header 购物车图标读 `cartStore.count`，全局可见，不依赖购物车页是否打开。

---

## ③ 商品详情页改造

**文件**：`app/[locale]/mall/products/[id]/page.tsx`

**现状**：已有 SKU 选择器 + 数量输入 + 阶梯价，三个按钮（加入询价篮/立即询价/WhatsApp）均 disabled。

**改造点**：

| 按钮 | 行为 |
|------|------|
| 加入询价篮 | POST `/cart/items` { sku_id, quantity } → `syncFromCart(returnedCart)` + `triggerRefresh()` → toast 成功 |
| 立即询价 | 本期不做，保持 disabled（入口设计待定） |
| WhatsApp | 本期不做，保持 disabled（入口设计待定） |

**交互约束**：
- 未选 SKU → 按钮置灰 + tooltip "请先选择规格"
- 数量 < MOQ → 行内警告提示 "最低起订量: {moq} {unit}"，**不阻止加购**（询价不是下单，允许低于 MOQ 提交；与购物车页口径一致）。数量输入框默认值为 MOQ。
- **未登录** → 按钮正常显示，点击跳转登录页（未登录无角色信息，不能按角色隐藏）
- **已登录但非 BUYER 角色** → 按钮不渲染（SUPPLIER/OPERATOR/ADMIN 不需要加购）
- 加购中 loading 态防重复点击
- 同 SKU 重复加购 → 后端自动累加数量，前端 toast "已更新数量"

**角标**：
- 顶部 Header 区域增加购物车图标 + `cartStore.count` 数字角标
- 仅 BUYER 角色可见
- 点击跳转 `/buyer/cart`

---

## ④ 询价篮页面

**文件**：`app/[locale]/buyer/cart/page.tsx`（替换现有 placeholder）

**数据加载**：`GET /cart` via SWR，key 含 `cartStore.refreshFlag`

### 布局

```
┌─────────────────────────────────────────────────────────┐
│ 页标题: 询价篮                                           │
├─────────────────────────────────────────────────────────┤
│ ☑ 全选(仅可购)  |  已选 {n} 件  |  [删除选中]            │
├─────────────────────────────────────────────────────────┤
│ 商品列表（每行一个 CartItemRow）:                          │
│                                                         │
│ ☑ [主图] 商品名                                 数量   操作  │
│          SKU规格(颜色/材质/型号) | MOQ: 100 PCS   [qty]  🗑   │
│          参考价: 1-99 $12 | 100-499 $10 | 500+ $8            │
│                                                         │
│ ☐ [主图] 商品名                    ⚠ 已下架    --    🗑   │
│          灰色行 + 不可购原因标签                           │
├─────────────────────────────────────────────────────────┤
│ 底部操作栏（sticky）:                                     │
│   已选 {n} 件                              [提交询价 →]  │
└─────────────────────────────────────────────────────────┘
```

### 空状态

购物车无商品时显示空态插图 + "去商城选品" 按钮（链接到 `/mall`）。

### 交互

| 操作 | 行为 |
|------|------|
| 勾选/取消 | 本地状态，不调后端 |
| 全选 | 仅勾选 `is_purchasable === true` 的项 |
| 修改数量 | PATCH `/cart/items/{item_id}` debounce 500ms |
| 数量 < MOQ | 行内警告，不阻止保存（后端允许） |
| 删除单项 | 确认弹窗 → DELETE `/cart/items/{item_id}` |
| 删除选中 | 确认弹窗 → 逐项 DELETE（后端无批量接口）。部分失败时 toast 提示失败数量，重新 GET /cart 刷新列表，不做本地乐观删除 |
| 不可购项 | 灰色行，checkbox 禁用，显示原因标签 |
| 提交询价 | 携带选中的 item_ids 跳转 `/buyer/rfqs/create?source=cart&items=1,2,3` |

**不可购原因映射**（i18n）：

| unavailable_reason | 中文 | 英文 |
|----|------|------|
| SKU_DELETED | 该规格已删除 | This SKU has been removed |
| SKU_INACTIVE | 该规格已下架 | This SKU is inactive |
| PRODUCT_DELETED | 该商品已删除 | This product has been removed |
| PRODUCT_INACTIVE | 该商品已下架 | This product is inactive |

---

## ⑤ 询价表单页

**文件**：`app/[locale]/buyer/rfqs/create/page.tsx`

### 入口与数据来源

本期仅支持购物车路径，DIRECT 模式后续再做。

| 入口 | URL 参数 | 数据来源 |
|------|----------|----------|
| 询价篮"提交询价" | `?source=cart&items=1,2,3` | GET /cart 后按 item_ids 过滤 |

### 表单布局（单页，4 个区块）

**区块 1：商品清单（只读表格）**

| 列 | 来源 |
|----|------|
| 商品名 | `product_name`（从购物车数据带入） |
| SKU 规格 | `sku_code` + `color` + `material` |
| 数量 | 从购物车带入，此处只读 |

- 商品信息从购物车数据取（GET /cart 后按 item_ids 过滤）
- **item_ids 失效处理**：用户可能在另一个 tab 已提交/删除购物车项，GET /cart 后按 ids 过滤可能缺项。部分缺失 → 提示"部分商品已不在询价篮，请确认"，展示剩余项可继续提交；全部缺失 → 提示"商品已不在询价篮，请重新选择"，禁用提交按钮，引导返回购物车。
- 不可删减行（删了就没东西可询了）
- **不展示行级目标单价/备注**：后端 CART 模式只接收 `cart_item_ids`，不支持每行附加 `target_unit_price/remark`。行级价格/备注仅 DIRECT 模式支持，本期不做。

**区块 2：交货信息**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 交货地点 | text | 否 | placeholder: "Nairobi, Kenya" |
| 期望交期 | date picker | 否 | 不能选过去日期 |
| 目标币种 | select | 否 | 选项: USD / KES / CNY，默认 USD |

**区块 3：联系方式**

| 字段 | 类型 | 必填 | 预填来源 |
|------|------|------|----------|
| 联系人 | text | 否 | `user.name` |
| 电话 | text | 否 | `user.phone` |
| 邮箱 | text | 否 | `user.email` |

**区块 4：附加要求**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 认证要求 | tag input | 否 | 可自由输入添加，如 SGS / ISO9001 |
| 备注 | textarea | 否 | 自由文本 |

> 附件上传本期不做，不展示该字段。

### 提交逻辑

```
点击"提交询价"
  → 表单校验（前端）
  → POST /rfqs {
      source_type: "CART",
      cart_item_ids: [1, 2, 3],
      contact_name, contact_phone, contact_email,
      requested_delivery_place, expected_delivery_date,
      target_currency, required_certifications, remark
    }
  → 成功: toast + 清除 sessionStorage 草稿 + GET /cart → syncFromCart + triggerRefresh + 跳转 /buyer/rfqs
  → 失败: toastError(translateError(err))
```

### 草稿持久化

- key: `rfq_draft_{user_id}`
- 存储：联系方式、交货信息、附加要求（不存商品列表，每次从入口重新带入）
- 提交成功后清除
- 页面加载时恢复

---

## ⑥ 询价列表 + 详情

### 列表页 `/buyer/rfqs`

**数据**：`GET /rfqs?page=X&page_size=20`（默认展示本组织全部 RFQ，不带 `mine=true`）

| 列 | 字段 | 说明 |
|----|------|------|
| 询价单号 | rfq_no | 可点击进详情 |
| 商品数 | items.length | 如 "3 件商品" |
| 状态 | status | 状态徽章 |
| 提交时间 | created_at | 格式化日期 |
| 操作 | — | 查看详情；SUBMITTED 状态可取消 |

**筛选**：
- 状态下拉：全部 / 已提交 / 已报价 / 已接受 / 已取消
- 范围 tab：全部（组织级） / 我发起的（`mine=true`）

**状态徽章颜色**：

| 状态 | 色 | 中文 | 英文 |
|------|----|------|------|
| DRAFT | gray | 草稿 | Draft |
| SUBMITTED | blue | 已提交 | Submitted |
| QUOTED | green | 已报价 | Quoted |
| ACCEPTED | emerald | 已接受 | Accepted |
| REJECTED | red | 已拒绝 | Rejected |
| EXPIRED | amber | 已过期 | Expired |
| CANCELLED | gray | 已取消 | Cancelled |

### 详情页 `/buyer/rfqs/[id]`

**数据**：`GET /rfqs/{id}`

**布局**：

```
┌─ 询价单详情 ────────────────────────────────────────────┐
│ RFQ-20260610-0001        状态: [已提交]      [取消询价]  │
├─────────────────────────────────────────────────────────┤
│ 商品清单                                                │
│ ┌───────────────────────────────────────────────────┐   │
│ │ 商品名(快照) | SKU规格(快照) | 数量 | 目标单价     │   │
│ │ 水泥 PO42.5  | 灰色/袋装     | 500  | —           │   │
│ │ 螺纹钢       | Φ12/12m       | 200  | —           │   │
│ └───────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│ 交货信息                                                │
│ 交货地点: Nairobi, Kenya                                │
│ 期望交期: 2026-08-01                                    │
│ 目标币种: USD                                           │
├─────────────────────────────────────────────────────────┤
│ 联系方式                                                │
│ 联系人: John  |  电话: +254...  |  邮箱: john@...       │
├─────────────────────────────────────────────────────────┤
│ 附加要求                                                │
│ 认证: SGS, ISO9001                                      │
│ 备注: 需要提供样品                                       │
├─────────────────────────────────────────────────────────┤
│ 提交时间: 2026-06-10 14:30                              │
└─────────────────────────────────────────────────────────┘
```

**取消操作**：
- 仅 SUBMITTED 状态显示"取消询价"按钮
- 点击弹确认框，可填取消原因（选填）
- PATCH `/rfqs/{id}/cancel` { cancel_reason? }
- 成功后刷新页面，状态变为 CANCELLED

---

## i18n key 规划

新增 namespace `cart` 和 `rfq`，分别写入 `messages/zh.json` 和 `messages/en.json`（与现有 `error.cart` / `error.rfq` 错误 key 分开）：

### zh.json

```json
{
  "cart": {
    "title": "询价篮",
    "empty": "询价篮为空",
    "goToMall": "去商城选品",
    "selectAll": "全选",
    "selected": "已选 {count} 件",
    "deleteSelected": "删除选中",
    "submitInquiry": "提交询价",
    "confirmDelete": "确定删除该商品？",
    "confirmDeleteSelected": "确定删除选中的 {count} 件商品？",
    "addSuccess": "已加入询价篮",
    "quantityUpdated": "数量已更新",
    "moqWarning": "最低起订量: {moq} {unit}",
    "unavailable_SKU_DELETED": "该规格已删除",
    "unavailable_SKU_INACTIVE": "该规格已下架",
    "unavailable_PRODUCT_DELETED": "该商品已删除",
    "unavailable_PRODUCT_INACTIVE": "该商品已下架",
    "selectSkuFirst": "请先选择规格",
    "loginRequired": "请先登录",
    "itemCount": "{count} 件商品",
    "referencePrice": "参考价",
    "referencePriceUnavailable": "—",
    "deletePartialFail": "{failed} 件删除失败，已刷新列表"
  },
  "rfq": {
    "title": "询价管理",
    "create": "提交询价",
    "detail": "询价详情",
    "rfqNo": "询价单号",
    "itemCount": "{count} 件商品",
    "submitTime": "提交时间",
    "status": "状态",
    "actions": "操作",
    "viewDetail": "查看详情",
    "cancel": "取消询价",
    "cancelConfirm": "确定取消该询价？",
    "cancelReason": "取消原因（选填）",
    "cancelSuccess": "询价已取消",
    "submitSuccess": "询价已提交",
    "filterAll": "全部",
    "section_items": "商品清单",
    "section_delivery": "交货信息",
    "section_contact": "联系方式",
    "section_extra": "附加要求",
    "productName": "商品名",
    "skuSpec": "SKU 规格",
    "quantity": "数量",
    "deliveryPlace": "交货地点",
    "deliveryDate": "期望交期",
    "currency": "目标币种",
    "contactName": "联系人",
    "contactPhone": "电话",
    "contactEmail": "邮箱",
    "certifications": "认证要求",
    "remark": "备注",
    "status_DRAFT": "草稿",
    "status_SUBMITTED": "已提交",
    "status_QUOTED": "已报价",
    "status_ACCEPTED": "已接受",
    "status_REJECTED": "已拒绝",
    "status_EXPIRED": "已过期",
    "status_CANCELLED": "已取消"
  }
}
```

### en.json

```json
{
  "cart": {
    "title": "Inquiry Basket",
    "empty": "Your inquiry basket is empty",
    "goToMall": "Browse Products",
    "selectAll": "Select All",
    "selected": "{count} selected",
    "deleteSelected": "Remove Selected",
    "submitInquiry": "Submit Inquiry",
    "confirmDelete": "Remove this item?",
    "confirmDeleteSelected": "Remove {count} selected items?",
    "addSuccess": "Added to inquiry basket",
    "quantityUpdated": "Quantity updated",
    "moqWarning": "MOQ: {moq} {unit}",
    "unavailable_SKU_DELETED": "This SKU has been removed",
    "unavailable_SKU_INACTIVE": "This SKU is inactive",
    "unavailable_PRODUCT_DELETED": "This product has been removed",
    "unavailable_PRODUCT_INACTIVE": "This product is inactive",
    "selectSkuFirst": "Please select specs first",
    "loginRequired": "Please login first",
    "itemCount": "{count} items",
    "referencePrice": "Ref. Price",
    "referencePriceUnavailable": "—",
    "deletePartialFail": "{failed} items failed to remove, list refreshed"
  },
  "rfq": {
    "title": "My Inquiries",
    "create": "Submit Inquiry",
    "detail": "Inquiry Detail",
    "rfqNo": "Inquiry No.",
    "itemCount": "{count} items",
    "submitTime": "Submitted",
    "status": "Status",
    "actions": "Actions",
    "viewDetail": "View Detail",
    "cancel": "Cancel Inquiry",
    "cancelConfirm": "Cancel this inquiry?",
    "cancelReason": "Reason (optional)",
    "cancelSuccess": "Inquiry cancelled",
    "submitSuccess": "Inquiry submitted",
    "filterAll": "All",
    "section_items": "Product List",
    "section_delivery": "Delivery Info",
    "section_contact": "Contact Info",
    "section_extra": "Additional Requirements",
    "productName": "Product",
    "skuSpec": "SKU Spec",
    "quantity": "Qty",
    "deliveryPlace": "Delivery Place",
    "deliveryDate": "Expected Delivery",
    "currency": "Currency",
    "contactName": "Contact",
    "contactPhone": "Phone",
    "contactEmail": "Email",
    "certifications": "Certifications",
    "remark": "Remarks",
    "status_DRAFT": "Draft",
    "status_SUBMITTED": "Submitted",
    "status_QUOTED": "Quoted",
    "status_ACCEPTED": "Accepted",
    "status_REJECTED": "Rejected",
    "status_EXPIRED": "Expired",
    "status_CANCELLED": "Cancelled"
  }
}
```

---

## 边界条件与注意事项

1. **未登录用户点加购** → 按钮正常显示，点击跳转登录页，登录后不自动回跳（MVP 简化）
2. **已登录但非 BUYER 角色** → 加购按钮不渲染（`hasRole('BUYER')` 判断）
3. **购物车无可购商品时点"提交询价"** → 按钮置灰 + tooltip
4. **询价篮到询价表单的数据传递** → URL query params（`items=1,2,3`），表单页重新 GET /cart 取完整数据再按 ids 过滤，不依赖内存传递
5. **sessionStorage 草稿** → 只存表单输入部分（联系/交货/附加），不存商品列表
6. **询价篮参考价展示** → 购物车后端不存价格。前端加载询价篮时，按 product_id 去重调 `GET /products/{id}` 拿 SKU 的 `price_tiers`，拉到 product detail 后，用 cart item 的 `sku_id` 匹配 `product.skus.find(s => s.id === sku_id)` 找到对应 SKU，展示该 SKU 的全部阶梯价（如 "1-99 $12 | 100-499 $10 | 500+ $8"），不做数量匹配联动。后端不改。**降级策略**：按 product_id 用 SWR 缓存（避免重复请求同一商品下的多个 SKU）；请求失败时该行参考价显示"—"，不阻塞页面主流程和提交询价。**TODO：参考价展示方式待优化——当前先原样展示全部阶梯价，后续可能改为根据数量匹配对应档位价格，需参考实际用户反馈再定。**
7. **提交后清购物车** → 后端 create_rfq CART 模式会自动删除对应 cart items，前端提交成功后 triggerRefresh 即可
8. **本期不做的功能** → "立即询价"按钮、WhatsApp 按钮、附件上传，均保持 disabled 或不展示

---

## 后续 TODO（本期未做，下期迭代）

| 编号 | 功能 | 说明 |
|------|------|------|
| T1 | **行级目标价格** | 询价表单商品行加"目标单价"输入列。需后端 CART 模式加 `cart_item_overrides` 参数支持每行传 `target_unit_price`，前端加输入框 |
| T2 | **BUYER DIRECT 模式** | 询价管理页"新建询价"入口，买方直接搜索商品+选 SKU+填数量创建询价，不走询价篮。后端已支持 BUYER DIRECT，前端需做商品搜索选择器 |
| T3 | **参考价展示优化** | 当前询价篮全部阶梯价原样展示，后续可能改为根据数量匹配对应档位价格，需参考实际用户反馈再定 |
| T4 | **询价篮表格布局微调** | 已改为 Alibaba 表格式，参考实际使用反馈优化列宽、间距、移动端适配 |
| T5 | **Operator 询价管理页** | 运营端询价列表/详情/报价回填前端（后端 API 已就绪） |
| T6 | **附件上传** | 询价表单附件上传功能，需对接文件上传服务 |
| T7 | **"立即询价"按钮** | 商品详情页直接询价入口，设计待定 |
| T8 | **WhatsApp 集成** | 商品详情页 WhatsApp 按钮，信息格式和链接生成待设计 |

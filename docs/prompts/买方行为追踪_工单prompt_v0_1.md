# 买方行为追踪 — 工单 prompt v0.1

> **前置文档**: `docs/adr/ADR-0007-买方行为追踪方案决策.md`
> **分支**: `feat/buyer-events`（基于最新 `dev`）

---

## 0. 实现顺序

| 步骤 | 交付物 | 依赖 |
|------|--------|------|
| ① | `BuyerEvent` ORM 模型 + Alembic 迁移 | 无 |
| ② | `buyer_event_service.py`（记录 + 查询 + 去重） | ① |
| ③ | RBAC 权限点新增 + 角色授予 | 无 |
| ④ | 后端 API 路由（买方 + 运营） | ①②③ |
| ⑤ | 现有端点埋点（products / cart / rfqs / quotes） | ②④ |
| ⑥ | 前端 `X-Session-Id` header 注入 | 无 |
| ⑦ | 前端「最近浏览」商城列表页顶部组件 | ④⑥ |
| ⑧ | 前端「最近搜索」搜索框下拉面板 | ④⑥ |
| ⑨ | i18n 三语翻译（zh / en / sw） | ⑦⑧ |
| ⑩ | 测试（后端单测 + 集成测） | ①②④⑤ |

---

## ① ORM 模型

### 文件: `backend/app/db/models/buyer_event.py`

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BuyerEvent(Base):
    __tablename__ = "buyer_events"
    __table_args__ = (
        Index("ix_buyer_events_user_type_time", "user_id", "event_type", "created_at"),
        Index("ix_buyer_events_resource", "resource_type", "resource_id"),
        Index("ix_buyer_events_session", "session_id"),
        Index("ix_buyer_events_org_time", "buyer_org_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buyer_org_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("buyer_organizations.id", name="fk_buyer_events_org_id"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_buyer_events_user_id"),
        nullable=False,
    )
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

**注册模型**: 在 `backend/app/db/models/__init__.py` 中 import `BuyerEvent`。

### Alembic 迁移

```bash
cd backend
alembic revision --autogenerate -m "add buyer_events table"
alembic upgrade head
```

检查生成的迁移文件，确保只包含 `buyer_events` 表创建，无无关变更。对 test 库也执行迁移。

---

## ② Service 层

### 文件: `backend/app/services/buyer_event.py`

#### 事件类型常量

```python
class EventType:
    VIEW_PRODUCT = "VIEW_PRODUCT"
    SEARCH = "SEARCH"
    VIEW_CATEGORY = "VIEW_CATEGORY"
    ADD_TO_CART = "ADD_TO_CART"
    CREATE_RFQ = "CREATE_RFQ"
    SUBMIT_RFQ = "SUBMIT_RFQ"
    ACCEPT_QUOTE = "ACCEPT_QUOTE"
```

#### 核心函数

**`record_event()`** — 记录事件（含去重）

```python
async def record_event(
    db: AsyncSession,
    *,
    buyer_org_id: int,
    user_id: int,
    event_type: str,
    resource_type: str | None = None,
    resource_id: int | None = None,
    extra: dict | None = None,
    request: Request | None = None,
) -> None:
```

逻辑：
1. **去重**: 查询同一 `user_id + event_type + resource_id`，`created_at > now() - 5min` 是否存在，存在则跳过（`SEARCH` 事件按 `extra->keyword` 去重）
2. **上下文提取**（从 request）:
   - `session_id`: `request.headers.get("x-session-id")`
   - `referrer`: `request.headers.get("referer")`
   - `device_type`: 从 `User-Agent` 解析（见下方工具函数）
   - `ip`: `request.client.host`
3. 构造 `BuyerEvent` 实例，`db.add()` + `await db.flush()`
4. **不单独 commit**，由调用方决定提交时机（GET 请求里用 BackgroundTask 独立事务提交）

**`parse_device_type(ua: str) -> str`** — UA 解析工具函数

```python
def parse_device_type(ua: str) -> str:
    """从 User-Agent 解析设备类型。"""
    ua_lower = ua.lower()
    if any(k in ua_lower for k in ("iphone", "android", "mobile")):
        return "mobile"
    if any(k in ua_lower for k in ("ipad", "tablet")):
        return "tablet"
    return "desktop"
```

**`get_recent_views()`** — 最近浏览商品

```python
async def get_recent_views(
    db: AsyncSession,
    user_id: int,
    limit: int = 8,
) -> list[dict]:
```

逻辑：
1. 查询 `event_type = VIEW_PRODUCT`，按 `created_at DESC`
2. 按 `resource_id` 去重（只取每个商品最近一次）
3. JOIN `products` 表取商品摘要（id, name, main_image, category_code, unit, moq）
4. 过滤已软删 + 非 ACTIVE 的商品（用户看不到已下架的）
5. 返回最多 `limit` 条

**`get_recent_searches()`** — 最近搜索词

```python
async def get_recent_searches(
    db: AsyncSession,
    user_id: int,
    limit: int = 10,
) -> list[str]:
```

逻辑：
1. 查询 `event_type = SEARCH`，按 `created_at DESC`
2. 提取 `extra->>'keyword'`，去重
3. 返回最多 `limit` 个关键词字符串

**`clear_recent_searches()`** — 清空搜索历史

```python
async def clear_recent_searches(
    db: AsyncSession,
    user_id: int,
) -> int:
```

逻辑：物理删除该用户所有 `event_type = SEARCH` 的记录，返回删除行数。

**`get_popular_products()`** — 热门商品（运营用）

```python
async def get_popular_products(
    db: AsyncSession,
    days: int = 30,
    limit: int = 20,
    metric: str = "view",   # view / cart / rfq
) -> list[dict]:
```

逻辑：
1. 按 `metric` 映射 event_type（view→VIEW_PRODUCT, cart→ADD_TO_CART, rfq→CREATE_RFQ）
2. `GROUP BY resource_id`，`COUNT(*) DESC`，取 Top N
3. JOIN products 取商品名

**`get_funnel_stats()`** — 转化漏斗（运营用）

```python
async def get_funnel_stats(
    db: AsyncSession,
    days: int = 30,
) -> dict:
```

逻辑：
1. 统计指定天数内各 event_type 的**独立用户数**（`COUNT(DISTINCT user_id)`）
2. 返回格式：

```json
{
  "period_days": 30,
  "stages": [
    {"event_type": "VIEW_PRODUCT", "unique_users": 120},
    {"event_type": "ADD_TO_CART", "unique_users": 45},
    {"event_type": "CREATE_RFQ", "unique_users": 30},
    {"event_type": "SUBMIT_RFQ", "unique_users": 25},
    {"event_type": "ACCEPT_QUOTE", "unique_users": 8}
  ]
}
```

---

## ③ RBAC 权限点

### `backend/app/rbac/constants.py` — 新增权限常量

```python
class Permissions:
    # ... 现有权限 ...

    # ----- 业务-买方:buyer_event -----
    BUYER_EVENT_READ = "buyer_event:read"

    # ----- 业务-运营:analytics -----
    ANALYTICS_READ = "analytics:read"
```

在 `PERMISSION_META` 字典中补充元数据：

```python
Permissions.BUYER_EVENT_READ: {
    "name": "查看买方行为记录",
    "module": ModuleLabel.BIZ_TRADE,
},
Permissions.ANALYTICS_READ: {
    "name": "查看运营分析数据",
    "module": ModuleLabel.BIZ_TRADE,
},
```

### `backend/app/rbac/permissions_config.py` — 角色授予

```python
ROLE_PERMISSIONS = {
    "BUYER": [
        ...,
        Permissions.BUYER_EVENT_READ,      # 查看自己的最近浏览/搜索
    ],
    "OPERATOR": [
        ...,
        Permissions.ANALYTICS_READ,        # 查看运营分析数据
    ],
    # ADMIN 不授予（严格职责分离）
}
```

---

## ④ API 路由

### 买方路由: `backend/app/api/v1/buyer_events.py`

```python
router = APIRouter(
    prefix="/buyer/events",
    tags=["buyer-events"],
    dependencies=[Depends(require_any_role("BUYER"))],
)
```

| 端点 | 方法 | 权限 | 用途 | 响应 data |
|------|------|------|------|-----------|
| `/buyer/events/recent-views` | GET | `BUYER_EVENT_READ` | 最近浏览商品 | `[{id, name, main_image, category_code, unit, moq}]` |
| `/buyer/events/recent-searches` | GET | `BUYER_EVENT_READ` | 最近搜索词 | `["cement", "tiles", ...]` |
| `/buyer/events/recent-searches` | DELETE | `BUYER_EVENT_READ` | 清空搜索历史 | `{"deleted": 5}` |

**recent-views 响应结构（复用 ProductPublic 子集）：**

```python
class RecentViewProduct(BaseModel):
    id: int
    name: str
    main_image: str | None = None
    category_code: str | None = None
    unit: str | None = None
    moq: float | None = None
```

### 运营路由: `backend/app/api/v1/operator_analytics.py`

```python
router = APIRouter(
    prefix="/operator/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_any_role("OPERATOR"))],
)
```

| 端点 | 方法 | 权限 | 用途 | 请求参数 |
|------|------|------|------|----------|
| `/operator/analytics/popular-products` | GET | `ANALYTICS_READ` | 热门商品 Top N | `?days=30&limit=20&metric=view` |
| `/operator/analytics/funnel` | GET | `ANALYTICS_READ` | 转化漏斗 | `?days=30` |

### 路由注册

在 `backend/app/main.py` 中注册两个新 router：

```python
from app.api.v1 import buyer_events, operator_analytics

app.include_router(buyer_events.router, prefix="/api/v1")
app.include_router(operator_analytics.router, prefix="/api/v1")
```

---

## ⑤ 现有端点埋点

所有 GET 端点的事件记录通过 `BackgroundTasks` 异步写入（独立 session + commit），不阻塞响应。
写端点的事件记录跟业务事务一起提交（已经在写 DB）。

### 5.1 商品列表 — `backend/app/api/v1/products.py` → `list_products()`

在函数签名中加 `background_tasks: BackgroundTasks` 和 `request: Request`。

**触发条件与事件：**
- 有 `keyword` 参数 → 记 `SEARCH` 事件，`extra={"keyword": keyword, "results": total}`
- 有 `category_code` 参数 → 记 `VIEW_CATEGORY` 事件，`extra={"category_code": category_code}`
- 仅对已登录买方记录（从 authorization header 解析 user_id，解析失败不记）

```python
# 埋点位置：return success({...}) 之前
if buyer_user_id and buyer_org_id:
    if keyword:
        background_tasks.add_task(
            _record_event_bg, buyer_org_id, buyer_user_id,
            EventType.SEARCH, None, None,
            {"keyword": keyword, "results": total}, request,
        )
    elif category_code:
        background_tasks.add_task(
            _record_event_bg, buyer_org_id, buyer_user_id,
            EventType.VIEW_CATEGORY, "category", None,
            {"category_code": category_code}, request,
        )
```

**`_record_event_bg()` 辅助函数**（放在同文件或 service 里）：

```python
async def _record_event_bg(
    buyer_org_id, user_id, event_type, resource_type, resource_id, extra, request,
):
    """BackgroundTask 用：独立 session + commit，失败静默（不影响主请求）。"""
    async with AsyncSessionLocal() as db:
        try:
            await record_event(
                db, buyer_org_id=buyer_org_id, user_id=user_id,
                event_type=event_type, resource_type=resource_type,
                resource_id=resource_id, extra=extra, request=request,
            )
            await db.commit()
        except Exception:
            pass  # 行为记录失败不影响业务
```

**注意**: `list_products` 当前是公开端点（无需登录）。需要从 `authorization` header 解析买方身份，解析失败（未登录/非买方）则不记事件。复用当前已有的 token 解析逻辑。还需额外查 `user.buyer_org_id`（可从 token payload 或 DB 查）。

### 5.2 商品详情 — `backend/app/api/v1/products.py` → `get_product()`

同上加 `background_tasks: BackgroundTasks` 和 `request: Request`。

```python
# 埋点位置：return success(data) 之前
if buyer_user_id and buyer_org_id:
    background_tasks.add_task(
        _record_event_bg, buyer_org_id, buyer_user_id,
        EventType.VIEW_PRODUCT, "product", product_id,
        {}, request,
    )
```

### 5.3 加购 — `backend/app/api/v1/cart.py` → `add_item()`

加购已在 service 层 commit。在 service 的 `add_item()` 里，`write_audit()` 之后、`commit` 之前加：

```python
await record_event(
    db, buyer_org_id=current.buyer_org_id, user_id=current.id,
    event_type=EventType.ADD_TO_CART, resource_type="product",
    resource_id=data.product_id,
    extra={"quantity": float(data.quantity)}, request=request,
)
```

### 5.4 创建询价 — `backend/app/api/v1/rfqs.py` → `create_rfq()`

在 `rfq_svc.create_rfq()` 内部，`write_audit()` 同层加：

```python
await record_event(
    db, buyer_org_id=current.buyer_org_id, user_id=current.id,
    event_type=EventType.CREATE_RFQ, resource_type="rfq",
    resource_id=rfq.id,
    extra={"item_count": len(data.items)}, request=request,
)
```

### 5.5 提交询价 — `rfqs.py` → `submit_rfq()`

```python
await record_event(
    db, buyer_org_id=current.buyer_org_id, user_id=current.id,
    event_type=EventType.SUBMIT_RFQ, resource_type="rfq",
    resource_id=rfq_id, extra={}, request=request,
)
```

### 5.6 接受报价 — `backend/app/api/v1/quotes.py` → `accept_rfq()`

```python
await record_event(
    db, buyer_org_id=current.buyer_org_id, user_id=current.id,
    event_type=EventType.ACCEPT_QUOTE, resource_type="rfq",
    resource_id=rfq_id,
    extra={"quote_id": quote.id}, request=request,
)
```

---

## ⑥ 前端 `X-Session-Id` 注入

### 文件: `frontend/src/lib/api.ts` → `rawFetch()` 函数

在 `finalHeaders` 构造区域加入 session_id：

```typescript
// Session ID: 标签页级会话标识，关闭标签页自动清除
function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let sid = sessionStorage.getItem("x-session-id");
  if (!sid) {
    sid = crypto.randomUUID();
    sessionStorage.setItem("x-session-id", sid);
  }
  return sid;
}
```

在 `rawFetch()` 的 `finalHeaders` 中加入：

```typescript
const sid = getSessionId();
if (sid) finalHeaders["X-Session-Id"] = sid;
```

---

## ⑦ 前端「最近浏览」组件

### 展示位置

商城列表页 `/mall`（`frontend/src/app/[locale]/mall/page.tsx`）顶部，在 `FilterBar` 之上。

### 展示规则

- **仅登录买方可见**（检查 `isBuyer`）
- **无浏览记录时不渲染**（数据为空则整个区域不占空间）
- 水平一行，最多 6-8 个商品小卡片，可水平滚动
- 每个卡片：商品主图（缩略图）+ 商品名（一行截断）
- 点击卡片跳转商品详情页 `/mall/products/{id}`

### API 客户端

**文件: `frontend/src/lib/api/buyerEvents.ts`**

```typescript
export async function getRecentViews(): Promise<RecentViewProduct[]> {
  return api.get("/api/v1/buyer/events/recent-views");
}

export async function getRecentSearches(): Promise<string[]> {
  return api.get("/api/v1/buyer/events/recent-searches");
}

export async function clearRecentSearches(): Promise<void> {
  return api.delete("/api/v1/buyer/events/recent-searches");
}

interface RecentViewProduct {
  id: number;
  name: string;
  main_image: string | null;
  category_code: string | null;
  unit: string | null;
  moq: number | null;
}
```

### 组件: `frontend/src/components/mall/RecentViews.tsx`

```typescript
"use client";

// useSWR 请求 getRecentViews()
// 无数据 → return null（不占空间）
// 有数据 → 水平滚动卡片列表
// 样式参考现有 ProductGrid 的卡片，但更紧凑（小图 + 单行名称）
```

### 集成到 mall/page.tsx

```tsx
// MallContent 组件内，FilterBar 之前
{isBuyer && <RecentViews />}
```

---

## ⑧ 前端「最近搜索」下拉面板

### 展示位置

商城页搜索框（当前在 `FilterBar` 组件内）聚焦时弹出下拉面板。

### 交互规则

- 搜索框 `onFocus` → 请求 `getRecentSearches()`，有数据则展示下拉面板
- **无搜索历史时不展示**
- 面板内容：标题 "Recent searches" + 关键词列表 + 右上角垃圾桶图标（清空）
- 点击关键词 → 填入搜索框并触发搜索
- 点击垃圾桶 → 调 `clearRecentSearches()`，面板收起
- 搜索框 `onBlur` / 点击面板外 → 收起面板（注意点击面板内元素时不要提前收起）
- 最多显示 5 条，有更多时显示 "Show more" 展开（最多 10 条）

### 组件: `frontend/src/components/mall/RecentSearches.tsx`

独立组件，由 `FilterBar` 内搜索框引用。

---

## ⑨ i18n 三语翻译

### `frontend/messages/zh.json`

```json
{
  "mall": {
    "recentViews": "最近浏览",
    "recentSearches": "最近搜索",
    "clearSearchHistory": "清空搜索历史",
    "showMore": "显示更多",
    "noRecentViews": ""
  }
}
```

### `frontend/messages/en.json`

```json
{
  "mall": {
    "recentViews": "Recently Viewed",
    "recentSearches": "Recent Searches",
    "clearSearchHistory": "Clear search history",
    "showMore": "Show more",
    "noRecentViews": ""
  }
}
```

### `frontend/messages/sw.json`

```json
{
  "mall": {
    "recentViews": "Zilizotazamwa Hivi Karibuni",
    "recentSearches": "Utafutaji wa Hivi Karibuni",
    "clearSearchHistory": "Futa historia ya utafutaji",
    "showMore": "Onyesha zaidi",
    "noRecentViews": ""
  }
}
```

注意：`noRecentViews` 留空字符串，因为无数据时整个区域不渲染，不需要文案。但 key 预留，后续可能用于空态引导。

合并时注意保留现有 `mall` 下的其他 key，只追加新 key。

---

## ⑩ 测试

### 文件: `backend/tests/test_buyer_events.py`

#### 测试用例清单

**事件记录：**
1. `test_record_view_product` — 浏览商品详情写入 buyer_events 表
2. `test_record_search` — 搜索带 keyword 写入事件 + extra 含 keyword
3. `test_record_view_category` — 带 category_code 的列表请求写入事件
4. `test_dedup_within_5min` — 同一用户 5 分钟内重复浏览同一商品只记 1 条
5. `test_dedup_different_products` — 同一用户浏览不同商品各记 1 条
6. `test_no_event_for_anonymous` — 未登录用户浏览商品不写事件
7. `test_no_event_for_non_buyer` — OPERATOR 浏览商品不写事件

**查询 API：**
8. `test_recent_views_returns_products` — 返回最近浏览商品列表，带商品摘要
9. `test_recent_views_dedup_by_product` — 同一商品多次浏览只返回一条
10. `test_recent_views_excludes_deleted` — 已软删商品不返回
11. `test_recent_searches_returns_keywords` — 返回最近搜索关键词列表
12. `test_recent_searches_dedup` — 相同关键词去重
13. `test_clear_recent_searches` — 清空后返回空列表
14. `test_popular_products` — 运营端点返回 Top N 商品
15. `test_funnel_stats` — 运营端点返回各阶段独立用户数

**RBAC：**
16. `test_buyer_can_read_own_events` — BUYER 可访问 recent-views/recent-searches
17. `test_operator_can_read_analytics` — OPERATOR 可访问 popular-products/funnel
18. `test_buyer_cannot_read_analytics` — BUYER 不能访问运营分析端点
19. `test_admin_cannot_read_events` — ADMIN 不能访问行为事件端点

**上下文字段：**
20. `test_session_id_captured` — 请求带 X-Session-Id header → 事件记录含 session_id
21. `test_device_type_parsed` — 手机 UA → device_type = "mobile"
22. `test_ip_captured` — 事件记录含客户端 IP

---

## 验收标准

- [ ] `alembic upgrade head` 成功，`buyer_events` 表创建正确
- [ ] 买方浏览商品详情 → `buyer_events` 表新增 `VIEW_PRODUCT` 记录
- [ ] 买方搜索 → `buyer_events` 表新增 `SEARCH` 记录，`extra` 含 keyword
- [ ] 5 分钟内重复浏览同一商品不重复记录
- [ ] 未登录/非买方用户不记录事件
- [ ] `GET /buyer/events/recent-views` 返回最近浏览商品（去重、排除已下架）
- [ ] `GET /buyer/events/recent-searches` 返回最近搜索词（去重）
- [ ] `DELETE /buyer/events/recent-searches` 清空搜索历史
- [ ] `GET /operator/analytics/popular-products` 返回热门商品排行
- [ ] `GET /operator/analytics/funnel` 返回转化漏斗数据
- [ ] 前端商城列表页顶部显示「最近浏览」横栏（登录买方 + 有数据时）
- [ ] 无浏览记录时「最近浏览」区域不渲染不占空间
- [ ] 前端搜索框聚焦显示「最近搜索」下拉（有数据时）
- [ ] 无搜索记录时下拉不显示
- [ ] 点击搜索词填入搜索框并触发搜索
- [ ] 点击垃圾桶清空搜索历史
- [ ] 每次请求自动带 `X-Session-Id` header
- [ ] i18n 三语（zh/en/sw）文案完整
- [ ] `pytest tests/test_buyer_events.py` 全部通过
- [ ] 事件记录失败不影响主请求响应

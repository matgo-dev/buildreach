# 首页布局改版设计 — 三栏等高 + 品类导航 + 轮播 Banner

> 日期: 2026-06-22
> 参考: 鑫方盛 (xfs.com) 首页

---

## 一、总体布局

首页顶部区域改为三栏等高布局，替换现有 Hero Banner：

```
┌──────────────┬───────────────────────────┬──────────────┐
│  品类导航     │     轮播 Banner            │  信息栏       │
│  (~240px)    │     (自适应)               │  (~280px)    │
│              │                           │              │
│  L1 短名列表  │  自动轮播 + 手动切换        │  WhatsApp    │
│  4个/行      │  圆点指示器                │  询价篮       │
│  hover弹flyout│                           │  信任标识     │
├──────────────┴───────────────────────────┴──────────────┤
│  下方内容区（服务承诺 / 平台能力 / CTA 等，保持现有）       │
└─────────────────────────────────────────────────────────┘
```

**关键约束：**
- 三栏等高对齐，高度由内容撑开（最小 ~400px）
- **不 sticky**，随页面滚动
- 响应式：md 以下品类栏隐藏，xl 以下右栏隐藏
- 品类栏底部"快速询价"卡片移除（空间让给品类行）

---

## 二、左侧品类导航

### 2.1 布局

参考鑫方盛，每行显示 4 个 L1 品类短名，用 `/` 分隔：

```
┌─────────────────────────┐
│ 🔲 全部商品分类          │  ← teal 主色头部
├─────────────────────────┤
│ 办公 / 清洁 / 安防 / 劳保 │  ← hover 高亮 + 左侧竖线
│ 润滑 / 粘胶 / 搬运 / 包装 │
│ 实验 / 仪表 / 传动 / 轴承 │  ← 最后一行不足4个留空
└─────────────────────────┘
```

- 行高紧凑（py-2.5 ~ py-3）
- hover 时：整行高亮背景 + 左侧 3px teal 竖线 + 文字变主色
- 短名来源：`short_name`（i18n）→ fallback `name` 前2字截取
- 点击行内任一品类名 → 跳转该品类商品列表

### 2.2 Hover Flyout

hover 某一行时，右侧弹出面板展示**该行所有 4 个 L1 品类的子品类**：

```
┌─────────────────────────────────────────────────┐
│ 润滑  (完整名)                                    │
│   车船航空润滑油  >  发动机油  制动液  车用齿轮油    │
│   工业润滑油      >  特种润滑油  导热油  工业齿轮油  │
│                                                   │
│ 粘胶  (完整名)                                    │
│   密封胶          >  有机硅胶  橡胶类胶  树脂类胶   │
│   粘接胶          >  瞬干胶  结构粘接胶             │
│                                                   │
│ 搬运  (完整名)                                    │
│   ...                                             │
│ 包装  (完整名)                                    │
│   ...                                             │
└─────────────────────────────────────────────────┘
```

- 每个 L1 作为一个分组，标题用完整 `name`（非 short_name）
- L2 作为行标题，后面跟 L3 子品类链接
- flyout z-index >= 40，白色背景 + 阴影
- 面板最大高度与品类栏等高，内容溢出时可滚动

---

## 三、Category short_name i18n

### 3.1 数据库变更

当前 `short_name` 是单字段 VARCHAR(20)，改为三语：

```sql
-- 新增
ALTER TABLE categories ADD COLUMN short_name_zh VARCHAR(20);
ALTER TABLE categories ADD COLUMN short_name_en VARCHAR(20);
ALTER TABLE categories ADD COLUMN short_name_sw VARCHAR(20);

-- 数据迁移: short_name → short_name_zh
UPDATE categories SET short_name_zh = short_name WHERE short_name IS NOT NULL;

-- 删除旧字段
ALTER TABLE categories DROP COLUMN short_name;
```

### 3.2 Schema 变更

`CategoryNode` / `CategoryTreeNode` 增加：
- `short_name_zh`, `short_name_en`, `short_name_sw` (原始字段)
- `short_name: str | None` (locale 化后的值，通过 `get_localized` 填充)

### 3.3 前端消费

```typescript
// 优先 short_name，fallback 到 name 前2字
const displayName = category.short_name || category.name.slice(0, 2);
```

---

## 四、轮播 Banner

### 4.1 数据表 `banner_slides`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增 |
| title_zh | VARCHAR(100) | 中文标题 |
| title_en | VARCHAR(100), nullable | 英文标题 |
| title_sw | VARCHAR(100), nullable | 斯语标题 |
| image_url | VARCHAR(500) NOT NULL | 图片地址 |
| link_url | VARCHAR(500), nullable | 点击跳转 |
| sort_order | Integer, default 0 | 排序（小在前） |
| is_active | Boolean, default true | 是否启用 |
| position | VARCHAR(50), default 'home_carousel' | 广告位标识 |
| start_at | DateTime, nullable | 定时上线（MVP 预留） |
| end_at | DateTime, nullable | 定时下线（MVP 预留） |
| + I18nMixin | | source_lang / trans_meta |
| + TimestampMixin | | created_at / updated_at |

### 4.2 API

**公开（无需登录）：**
- `GET /api/v1/banners?position=home_carousel` → 返回该位置启用的 slides，按 sort_order 排序

**Operator CRUD：**
- `POST /api/v1/operator/banners` — 创建
- `PUT /api/v1/operator/banners/{id}` — 更新
- `DELETE /api/v1/operator/banners/{id}` — 删除
- `GET /api/v1/operator/banners` — 列表（含未启用）

权限点：`banner:read`, `banner:write`

### 4.3 前端轮播组件

- 自动轮播（5s 间隔），hover 暂停
- 手动左右箭头切换
- 底部圆点指示器，可点击跳转
- 过渡动画：fade 或 slide
- 图片点击跳转 `link_url`（如有）
- 无数据时显示默认占位图

---

## 五、右侧信息栏

保持现有 `RightSidebar` 内容不变：
- Customer Support (WhatsApp)
- RFQ Cart
- Trust Marks

高度与左中栏对齐（flex stretch）。

---

## 六、响应式策略

| 断点 | 品类栏 | 轮播 | 右栏 |
|------|--------|------|------|
| < md | 隐藏 | 全宽 | 隐藏 |
| md ~ lg | 隐藏 | 全宽 | 隐藏 |
| lg ~ xl | 显示 | 自适应 | 隐藏 |
| ≥ xl | 显示 | 自适应 | 显示 |

---

## 七、实施顺序

1. 后端: Category short_name i18n 迁移
2. 后端: banner_slides 表 + CRUD API
3. 前端: CategorySidebar 改造（4个/行 + flyout）
4. 前端: 轮播 Banner 组件
5. 前端: 首页三栏布局重构
6. i18n 翻译 key 补充

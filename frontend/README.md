# Frontend · 认证 / RBAC 测试界面

> Next.js (App Router) + TypeScript + Tailwind + shadcn 风格

## 快速开始

```bash
cd frontend
pnpm install
cp .env.local.example .env.local
# 默认 NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

pnpm dev   # http://localhost:3000
```

> 后端必须先起在 8000 端口,否则 /auth/me 调用会失败。

## 关键约定

- token 存 `localStorage`,key:`ovx_access_token` / `ovx_refresh_token`
- 登录后立刻调 `/auth/me` 拿完整 user(roles + permissions + organization)
- super admin 首次登录 `must_change_password=true`,被 `RouteGuard` 强制跳 `/change-password`
- 不集成 NextAuth、Prisma
- 不做国际化(单一中文)

## 页面清单

| 路径 | 说明 |
|---|---|
| `/` | 落地页(品牌占位 + 入口链接)|
| `/login` | 登录(注册成功后会带 `?registered=1` 提示)|
| `/register` | 注册(单页 + 角色切换 BUYER/SUPPLIER)|
| `/change-password` | 修改密码(强制改密必经)|
| `/test/buyer-only` | RBAC 测试页(BUYER)|
| `/test/supplier-only` | RBAC 测试页(SUPPLIER)|
| `/test/operator-only` | RBAC 测试页(OPERATOR)|
| `/test/admin-only` | RBAC 测试页(ADMIN)|

每个测试页包含:个人资料 + 全部权限点列表 + 调用 4 个角色测试 API 的按钮(自己 200,其他 403)。

## 主要文件

```
src/
├── app/                  路由(App Router)
├── components/
│   ├── ui/               基础组件(Button/Input/Card/Label/Alert)
│   └── auth/             AuthProvider / RouteGuard / PermissionGuard
├── hooks/                useAuth / usePermissions
├── lib/                  api / auth / permissions / utils
├── stores/               authStore(zustand)
└── middleware.ts         路径前缀过滤(实际登录态由客户端 Hook 守卫)
```

## 与参考工程的差异

| 项 | 参考工程 | 本项目 |
|---|---|---|
| 登录方式 | NextAuth Credentials | 直接 fetch + localStorage |
| 注册接口 | 单接口 + role 字段 | 双接口 register/buyer 与 register/supplier |
| 注册成功 | 自动登录 | 不自动登录,跳 `/login?registered=1` |
| 数据层 | Prisma | 不引入(后端 SQLAlchemy)|
| 国际化 | next-intl | 不做 |
| 品牌名 | "基建严选" | TODO 占位,等定调 |

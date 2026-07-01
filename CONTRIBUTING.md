# 开发协作规范

## 分支策略（单主干）

```
main          ← 主干分支，ECS/OVH 都从这里选择版本部署
  │
feat/xxx      ← 新功能分支，从 main 切出
fix/xxx       ← Bug 修复分支，从 main 切出
hotfix/xxx    ← 生产紧急修复，从 main 切出
```

### 分支命名规范

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feat/` | 新功能 | `feat/sms-verification` |
| `fix/` | Bug 修复 | `fix/image-loading` |
| `hotfix/` | 生产紧急修复 | `hotfix/login-crash` |
| `refactor/` | 重构 | `refactor/unify-cicd` |
| `chore/` | 杂项（配置、依赖等） | `chore/upgrade-deps` |

---

## 日常开发流程（新功能 / 非紧急 Bug）

```bash
# 1. 从 main 切分支
git checkout main && git pull origin main
git checkout -b feat/xxx

# 2. 开发 + 提交
git add <files>
git commit -m "feat(scope): 简要描述"

# 3. 推送 + 创建 PR → main
git push -u origin feat/xxx
gh pr create --base main

# 4. 合并到 main（GitHub 网页或命令行）
gh pr merge --squash

# 5. 部署 ECS/OVH
#    GitHub Actions → Build & Deploy → 选 main 分支
#    ECS 自动部署，OVH 等待审批
#    approve OVH 部署
```

---

## 生产紧急修复（Hotfix）

```bash
# 1. 从 main 切分支
git checkout main && git pull origin main
git checkout -b hotfix/xxx

# 2. 修复 + 提交
git add <files>
git commit -m "fix(scope): 紧急修复描述"

# 3. 创建 PR → main
git push -u origin hotfix/xxx
gh pr create --base main

# 4. 合并到 main，部署 OVH
#    Build & Deploy → 选 main → approve OVH
```

---

## Commit 规范

格式：`<type>(<scope>): <简要描述>`

| type | 含义 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构（不改功能） |
| `chore` | 杂项（配置、依赖、CI） |
| `docs` | 文档 |
| `style` | 格式调整（不改逻辑） |
| `perf` | 性能优化 |

示例：
- `feat(product): 商品列表按上架时间排序`
- `fix(deploy): ECS从ACR拉取镜像避免GHCR跨境慢`
- `chore: 仓库路径更新为matgo-dev/buildreach`

---

## 测试策略：单元 vs 集成

按"**bug 藏在哪**"决定测法，不按"方便与否"。

| 代码性质 | 测法 | 说明 |
|---------|------|------|
| 纯逻辑：解析 / 计算 / 分支 / 校验 / 状态判定（不涉及 I/O） | **单元测试** | mock 掉 DB/HTTP，毫秒级，失败能精确定位。文件放 `backend/tests/*_unit.py`，不使用 `client`/`db` fixture |
| 跨边界接线：路由 / 权限门 / 请求解析（FastAPI `Form`）/ DB 事务落库 / 响应信封 / 迁移 | **集成测试** | bug 藏在"缝隙"里，mock 掉就失去意义。只覆盖**关键路径**（权限、状态流转、落库），不追求 endpoint 全覆盖 |
| 混合型 endpoint | 抽纯逻辑单测 + 一条关键路径集成 | 把 handler 里的纯逻辑**抽成纯函数**单测，但**不为了单测而把 endpoint 硬拆碎** |

**要求**：新增纯函数 / 纯属性必须带配套**单元测试**；endpoint 级接线用集成测试兜底关键路径。

**反模式**：① 用集成测试覆盖纯逻辑（慢、依赖 DB）；② 把接线全 mock 到"只在断言 mock"，测试全绿但生产是坏的。

---

## 部署流程

### 环境对应关系

| 环境 | 分支 | 机器 | 触发方式 |
|------|------|------|---------|
| 测试/预发 | main | 阿里云 ECS | Build & Deploy → main → 自动 |
| 生产 | main | OVHcloud | Build & Deploy → main → 手动审批 |

### 部署操作

1. GitHub → Actions → **Build & Deploy** → Run workflow → 选分支
2. 等构建完成（约5分钟）
3. ECS 自动部署（staging 环境）
4. OVH 需要点 **Review pending deployments → Approve and deploy**

### 回滚

```bash
# 方式一：GitHub Actions 重跑历史记录
# Actions → 找到上次成功的部署 → Re-run all jobs

# 方式二：SSH 手动回滚
ssh root@<IP>
cd /opt/buildreach
git log --oneline -10
git reset --hard <commit-sha>
bash deploy/deploy.sh
```

---

## 红线（必须遵守）

- **不直接在 main 上 commit**，走分支 + PR
- **新增代码带配套测试**：纯逻辑单测、接线关键路径集成（见「测试策略」）
- **PR 合并后不删分支**
- **新依赖/新目录/新环境变量**必须同步检查 Dockerfile / compose / 部署脚本
- **破坏性数据库操作**（drop column/table）commit message 加 `[allow-destructive-migration]`
- **严禁** `docker compose down -v` / `docker volume rm` / `docker system prune --volumes`
- `.env.production` 严禁入 Git

# 开发协作规范

## 分支策略

`main` 是唯一主干(真相源),所有 feature 从它切、也从它部署到 ECS 预发;
生产走从 main 切出的**不可变发布分支** `release-v*`,只有它能部署到 OVH。

```
main               ← 主干 / 真相源。feature 从此切;ECS(预发)从此部署
  │
  ├─ feat/xxx      ← 新功能,从 main 切,PR 回 main
  ├─ fix/xxx       ← 非紧急 Bug 修复,从 main 切,PR 回 main
  │
  └─(验证 OK 后从 main 切出)
        │
   release-v0.x.x  ← 发布分支,切出后不可变。OVH(生产)从此部署
        │
        └─ hotfix/xxx  ← 生产紧急修复,从 release-v* 切;
                          合回 release-v*(重部署 OVH)+ 回流 main
```

> 已废弃 `dev` / `pre-release` 长期分支:预发是「环境」不是「分支」,由 main → ECS 承担,
> 避免两条长期分支漂移。

### 分支命名规范

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feat/` | 新功能 | `feat/sms-verification` |
| `fix/` | 非紧急 Bug 修复 | `fix/image-loading` |
| `hotfix/` | 生产紧急修复(从 `release-v*` 切) | `hotfix/login-crash` |
| `release-v` | 发布分支(从 `main` 切) | `release-v0.3.0` |
| `refactor/` | 重构 | `refactor/unify-cicd` |
| `chore/` | 杂项(配置、依赖等) | `chore/upgrade-deps` |

---

## 日常开发流程(新功能 / 非紧急 Bug)

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

# 4. CI 绿灯后合并到 main
gh pr merge --squash

# 5. 部署到 ECS 预发做验证(手动)
#    GitHub → Actions → Build & Deploy → Run workflow → 选 main
#    ref 是 main(非 release-v*),这一次只会部署 ECS
```

---

## 发布到生产(Release)

main 在 ECS 上验证通过、可以发版时:

```bash
# 1. 从 main 切出发布分支(切出后不可变,只接受 hotfix)
git checkout main && git pull origin main
git checkout -b release-v0.x.x
git push -u origin release-v0.x.x

# 2. 部署到 OVH 生产(手动)
#    GitHub → Actions → Build & Deploy → Run workflow → 选 release-v0.x.x
#    ref 命中 release-v*,这一次只会部署 OVH
#    production 环境已配审批,需点 Review pending deployments → Approve
```

> 尽量在 ECS 验证通过后**尽快**切 release,减少切出前 main 又攒进未充分验证的改动。

---

## 生产紧急修复(Hotfix)

生产跑的是 `release-v*`,所以 hotfix 必须**从 release-v* 切**,基于「生产真正在跑的代码」修。

```bash
# 1. 从当前生产的发布分支切 hotfix
git checkout release-v0.x.x && git pull origin release-v0.x.x
git checkout -b hotfix/xxx

# 2. 修复 + 提交
git add <files>
git commit -m "fix(scope): 紧急修复描述"

# 3. PR → release-v0.x.x,验证后合并
git push -u origin hotfix/xxx
gh pr create --base release-v0.x.x

# 4. 重新部署 OVH
#    Build & Deploy → Run workflow → 选 release-v0.x.x → Approve

# 5. 回流 main(否则修复会在下次发版丢失)
#    从 main 切分支 cherry-pick / 合并该 hotfix,PR → main
```

**关键**:hotfix 要落到**两处** —— `release-v0.x.x`(修生产)+ `main`(不然下个版本又坏)。

---

## Commit 规范

格式:`<type>(<scope>): <简要描述>`

| type | 含义 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构(不改功能) |
| `chore` | 杂项(配置、依赖、CI) |
| `docs` | 文档 |
| `style` | 格式调整(不改逻辑) |
| `perf` | 性能优化 |

示例:
- `feat(product): 商品列表按上架时间排序`
- `fix(deploy): ECS从ACR拉取镜像避免GHCR跨境慢`
- `chore: 仓库路径更新为matgo-dev/buildreach`

---

## 测试策略:单元 vs 集成

按"**bug 藏在哪**"决定测法,不按"方便与否"。

| 代码性质 | 测法 | 说明 |
|---------|------|------|
| 纯逻辑:解析 / 计算 / 分支 / 校验 / 状态判定(不涉及 I/O) | **单元测试** | mock 掉 DB/HTTP,毫秒级,失败能精确定位。文件放 `backend/tests/*_unit.py`,不使用 `client`/`db` fixture |
| 跨边界接线:路由 / 权限门 / 请求解析(FastAPI `Form`)/ DB 事务落库 / 响应信封 / 迁移 | **集成测试** | bug 藏在"缝隙"里,mock 掉就失去意义。只覆盖**关键路径**(权限、状态流转、落库),不追求 endpoint 全覆盖 |
| 混合型 endpoint | 抽纯逻辑单测 + 一条关键路径集成 | 把 handler 里的纯逻辑**抽成纯函数**单测,但**不为了单测而把 endpoint 硬拆碎** |

**要求**:新增纯函数 / 纯属性必须带配套**单元测试**;endpoint 级接线用集成测试兜底关键路径。

**反模式**:① 用集成测试覆盖纯逻辑(慢、依赖 DB);② 把接线全 mock 到"只在断言 mock",测试全绿但生产是坏的。

---

## 部署流程

### 环境对应关系

| 环境 | 部署来源 ref | 机器 | 触发方式 |
|------|-------------|------|---------|
| 预发 (staging) | `main`(任意非 `release-v*` 分支) | 阿里云 ECS | Build & Deploy → 选该分支 → **手动** |
| 生产 (production) | `release-v0.x.x` | OVHcloud | Build & Deploy → 选该发布分支 → **手动** + 环境审批 |

> 触发全为手动(`workflow_dispatch`),**点在哪个 ref 上就只部署对应环境**:
> 非 release-v* → 只打 ECS;release-v* → 只打 OVH。一次点击不会同时打两个环境。
> (测试是自动的:push 到 main/feat/fix/hotfix/release-v 会自动跑 CI。)

### 部署操作

1. GitHub → Actions → **Build & Deploy** → Run workflow → 选 ref
   - 预发选 `main`;生产选 `release-v0.x.x`
2. 等构建完成(约 5 分钟)
3. 目标环境部署:ECS 直接部署;OVH 需点 **Review pending deployments → Approve and deploy**
4. 部署失败但镜像已构建成功:用 **Deploy Only (Re-deploy)** 补救(OVH 同样只允许 release-v*)

### 回滚

**方式一(推荐,可视化选版本):Deploy Only 指定历史镜像 tag**

镜像每次构建都按 commit 打了不可变 tag(`<branch>-<sha>`,如 `release-v0.2.0-abc1234`),
历史版本镜像都留在 GHCR + ACR,可直接回滚、不重新构建:

1. GitHub → Actions → **Deploy Only (Re-deploy)** → Run workflow
2. Branch 选目标 ref(回滚生产选 `release-v*`,OVH 门槛才放行)
3. `image_tag` 填要回滚到的历史 tag(如 `release-v0.2.0-abc1234`);留空则部署该分支最新镜像
4. `target` 选 `ovh`(或 `ecs`)→ Run,production 需 Approve

> 历史 tag 可在对应的 Build & Deploy 运行日志、或镜像仓库(GHCR/ACR)里查到。
> 注意:此方式回滚的是**运行的应用镜像**;服务器上的 compose/nginx 会同步到所选分支的当前 HEAD。
> 若两版本间 compose/nginx 有不兼容改动,改用「方式二」把 release 分支重置到旧 commit 再部署。

**方式二:重跑历史运行 / SSH 手动**

```bash
# a) GitHub Actions 重跑:Actions → 找到上次成功的部署 → Re-run all jobs(会重新构建)

# b) SSH 手动回滚(代码 + 镜像都回到旧版)
ssh root@<IP>
cd /opt/buildreach
git log --oneline -10
git reset --hard <commit-sha>
bash deploy/deploy.sh
```

---

## 红线(必须遵守)

- **不直接在 main 上 commit**,走分支 + PR
- **OVH 生产只从 `release-v*` 部署**,hotfix 从 `release-v*` 切并回流 main
- **新增代码带配套测试**:纯逻辑单测、接线关键路径集成(见「测试策略」)
- **PR 合并后分支自动删除**(仓库已开启 delete-branch-on-merge,无需手动保留)
- **新依赖/新目录/新环境变量**必须同步检查 Dockerfile / compose / 部署脚本
- **破坏性数据库操作**(drop column/table)commit message 加 `[allow-destructive-migration]`
- **严禁** `docker compose down -v` / `docker volume rm` / `docker system prune --volumes`
- `.env.production` 严禁入 Git

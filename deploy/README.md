# 部署指南

## 平时部署(手动一键触发)

**代码提交 / 合并 main 不会自动部署**,代码与部署解耦。

部署只在你明确触发时执行,任选一种方式:

```bash
# 命令行:本地一条命令
gh workflow run "Deploy to ECS" --repo tutu6/overseas-platform-v0.1

# 查看部署进度
gh run watch
```

或者打开 GitHub repo → **Actions** → 左边选 "Deploy to ECS" → 右上角 **Run workflow** → 选 main 分支 → 点 Run。

部署过程同前:Actions 跑 → SSH 到 ECS → `bash deploy/deploy.sh`(备份 → git pull → up --build → 健康检查)。

---

## 首次部署 Checklist(只做一次)

### 1. ECS 准备

- [ ] ECS 已装 Docker 20.10+ 和 Docker Compose v2
- [ ] ECS 安全组开放 22 / 3000 / 8000
- [ ] 创建部署目录:`sudo mkdir -p /opt/overseas-platform && sudo chown $USER:$USER /opt/overseas-platform`

### 2. SSH 密钥(GitHub Actions 用)

```bash
# 本地生成专用部署密钥
ssh-keygen -t ed25519 -f ~/.ssh/ecs_deploy -C "github-actions-deploy" -N ""

# 公钥追加到 ECS
ssh-copy-id -i ~/.ssh/ecs_deploy.pub user@<ECS-IP>
# 或手动:把 ~/.ssh/ecs_deploy.pub 内容贴到 ECS 的 ~/.ssh/authorized_keys

# 验证
ssh -i ~/.ssh/ecs_deploy user@<ECS-IP> "echo ok"
```

### 3. GitHub Secrets 配置

repo → Settings → Secrets and variables → Actions → New repository secret:

| Name | Value |
|---|---|
| `ECS_HOST` | ECS 公网 IP |
| `ECS_USER` | 登录用户名 |
| `ECS_SSH_KEY` | `cat ~/.ssh/ecs_deploy` 全文(含 BEGIN/END 行) |

### 4. ECS 首次启动

```bash
ssh user@<ECS-IP>
cd /opt/overseas-platform

# 克隆代码
git clone git@github.com:tutu6/overseas-platform-v0.1.git .
# (或 https 方式;若用 git,需在 ECS 上配 deploy key)

# 配 env
cp .env.production.example .env.production
vim .env.production    # 填真实值,关键项:
                       #   POSTGRES_PASSWORD = openssl rand -base64 24
                       #   JWT_SECRET_KEY    = openssl rand -hex 32
                       #   NEXT_PUBLIC_API_BASE_URL = http://<ECS-IP>:8000
                       #   CORS_ORIGINS             = http://<ECS-IP>:3000
chmod 600 .env.production

# 首次部署
bash deploy/deploy.sh
```

### 5. 迁移老演示数据(如有)

```bash
# 在老演示目录上(本机或老 ECS 路径)
docker compose exec -T <老 db 服务名> pg_dump -U <老 user> <老 db> | gzip > /tmp/legacy-demo.sql.gz
scp /tmp/legacy-demo.sql.gz user@<新 ECS>:/opt/overseas-platform/

# 在新 ECS 上
ssh user@<ECS-IP>
cd /opt/overseas-platform

# 清空新库 seed 创的默认数据(避免唯一键冲突)
# ⚠️ 仅首次部署专用,日常部署不能跑这一步
source .env.production
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
TRUNCATE TABLE audit_logs, user_roles, role_permissions,
  users, roles, permissions,
  supplier_organizations, buyer_organizations
RESTART IDENTITY CASCADE;
SQL

# 导入老数据
gunzip -c legacy-demo.sql.gz | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

# 重启 backend(RBAC 启动同步会跑一次,把权限对齐到当前代码)
docker compose restart backend
```

### 6. 改 super admin 密码

浏览器访问 `http://<ECS-IP>:3000`,用 `.env.production` 里的 super admin 登录,**立即改密**。

---

## 日常运维

### 查看日志

```bash
ssh user@<ECS-IP>
cd /opt/overseas-platform
docker compose logs -f backend       # 后端
docker compose logs -f frontend      # 前端
docker compose logs -f db            # 数据库
```

### 进容器

```bash
docker compose exec backend bash
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

### 手动备份

```bash
source .env.production
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > backups/manual-$(date +%Y%m%d-%H%M).sql.gz
```

(自动备份每次部署都会做,留 7 天)

---

## 应急

### 部署失败 → 手动 SSH 重跑

```bash
ssh user@<ECS-IP>
cd /opt/overseas-platform
bash deploy/deploy.sh
```

### 回滚到上一版

```bash
ssh user@<ECS-IP>
cd /opt/overseas-platform
git log --oneline -10                    # 找到上一版 commit
git reset --hard <commit-sha>
bash deploy/deploy.sh
```

### 数据库恢复

```bash
ssh user@<ECS-IP>
cd /opt/overseas-platform
source .env.production
ls backups/                              # 找最近备份
gunzip -c backups/YYYYMMDD-HHMMSS.sql.gz | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

### 破坏性迁移的情况

CI 会自动拦截含 `drop_column` / `drop_table` 等的 migration。

确实需要执行时,任选其一:

1. **commit message 加标记**:`feat(db): xxx [allow-destructive-migration]`,CI 放行
2. **手动 SSH 执行**:跳过 CI,直接在 ECS 上 `bash deploy/deploy.sh`

---

## 安全约束(必须遵守)

| 项 | 要求 |
|---|---|
| `.env.production` | ECS 上 `chmod 600`,**严禁入 Git** |
| `docker compose down -v` | **任何脚本 / 文档不能出现**,会删 volume |
| `docker volume rm` | 同上 |
| `docker system prune --volumes` | 同上 |
| 第 5 步迁移老数据时的 TRUNCATE | 仅首次部署可跑,日常部署严禁 |
| ECS 用户 sudo 权限 | 不需要给 root 也行,Docker daemon 走 docker group |

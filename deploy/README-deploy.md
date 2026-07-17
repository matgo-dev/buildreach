# 离线部署包操作手册

> 本文档面向**部署操作人员**，不需要懂代码。按顺序执行即可。

---

## 一、打包前需要准备的数据

打包脚本会从项目目录的 `data/` 和前端 `public/` 收集数据。**打包前必须确认以下文件就位**：

### 1.1 需要人工提供的（脚本无法自动获取）

| 数据 | 路径 | 来源 | 说明 |
|------|------|------|------|
| **商品批次数据** | 独立资产包,服务器解压到 `data/xfs/output_xfs_YYYYMMDD_HHMMSS/` | 鑫方盛抓取脚本产出 | 含 offer.json + 商品图片,体积可能十几 G,不进入应用离线包 |
| **轮播图图片** | `frontend/public/banners/*.png/jpg` | 设计师/运营提供 | 打包时复制到离线包 `data/banners/`,用于首页轮播与 OpenResty 静态访问 |
| **楼层背景图** | `frontend/public/images/floors/*.webp` | 设计师/运营提供 | 首页六个楼层背景图,随前端镜像发布 |

> 当前首页轮播不读 `banner_slides` 表,不需要执行 `seed_banners.py`。后续改成运营后台动态 Banner 时再启用 DB 初始化。

### 1.2 脚本自动获取的（不需要手动准备）

| 数据 | 路径 | 说明 |
|------|------|------|
| 品类树 JSON | `data/xfs/categories_full_tree.json` | 已在代码仓库的 data 目录,会进入应用离线包 |
| 品类 CSV | `data/categories.csv` | 已在代码仓库 |
| 属性模板 CSV | `data/attr_templates.csv` | 已在代码仓库 |
| Docker 镜像 | 脚本现场构建 | 从代码自动 build |

### 1.3 打包前的目录结构（确认清单）

```
data/
├── xfs/
│   └── categories_full_tree.json          ← ✅ 已有（Git 里,进入应用离线包）
├── categories.csv                         ← ✅ 已有
├── attr_templates.csv                     ← ✅ 已有
└── category_names_en.json                 ← ✅ 已有

frontend/public/
├── banners/                               ← ✅ 打包时复制到离线包 data/banners/
│   ├── hero-main.jpg
│   └── ...
└── images/floors/                         ← ✅ 随前端镜像发布
    ├── tools.webp
    ├── safety.webp
    ├── fasteners.webp
    ├── electrical.webp
    ├── doors.webp
    └── decoration.webp
```

---

## 二、打包（在有网环境执行）

### 2.1 需要两个参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--api-url` | 目标公网入口（构建后不可改！） | `https://www.example.com` |
| `--tag` | 发布标签 | `20260624` |

> **⚠️ `--api-url` 一旦打包就写死在前端 JS 里了。换 IP/域名必须重新打包。**

### 2.2 执行打包

```bash
cd /opt/buildreach   # 或你的项目目录
bash deploy/package-offline.sh --api-url https://<你的域名> --tag 20260624
```

### 2.3 打包产出

```
buildlink-offline-20260624.tar.gz    ← 这就是离线部署包（约 400M-1.5G，取决于镜像大小）
```

包内含：镜像 tar × 3 + 首页轮播图 `data/banners/` + 轻量初始化数据 + 脚本 + 配置模板 + manifest.json。
大体积商品批次不在此包内,需要作为独立资产包上传。

---

## 三、部署（在目标服务器执行，不需要外网）

### 3.0 前提

- 目标服务器已安装 Docker Engine 24+ 和 Docker Compose V2
- tar.gz 已传到目标服务器

### 3.1 解包

```bash
cd /opt   # 或你选择的目录
tar xzf buildlink-offline-20260624.tar.gz
cd buildlink-offline
```

### 3.2 填写配置（⚠️ 最重要的一步）

```bash
cp .env.production.example .env.production
vi .env.production
```

**必须手动填写的值（6 个敏感项）：**

| 变量 | 怎么生成 | 说明 |
|------|---------|------|
| `POSTGRES_PASSWORD` | `openssl rand -base64 24` | 数据库密码，**首次设置后不可改** |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` | JWT 签名密钥 |
| `SUPER_ADMIN_EMAIL` | 你定 | 管理员登录邮箱 |
| `SUPER_ADMIN_INITIAL_PASSWORD` | 你定（强密码） | 管理员初始密码 |
| `GOOGLE_TRANSLATE_API_KEY` | Google Cloud Console 获取 | 翻译服务密钥（无则填空，翻译不生效） |
| `RELEASE_TAG` | 与打包时的 `--tag` 一致 | 如 `20260624` |

**需要确认/修改的值（按实际域名改）：**

| 变量 | 示例 | 说明 |
|------|------|------|
| `API_BASE_URL` | `https://www.example.com` | 浏览器访问后端的公网入口（运行时注入） |
| `CORS_ORIGINS` | `https://www.example.com` | 前端地址 |
| `IMAGE_BASE_URL` | `https://www.example.com/static` | 图片 URL 前缀 |
| `BANNER_DIR` | `./data/banners` | 首页轮播图目录,默认不用改 |
| `BACKEND_HOST_PORT` | `8001` | 后端端口 |
| `FRONTEND_HOST_PORT` | `3001` | 前端端口 |

> **⚠️ 三个 URL 必须匹配**：`API_BASE_URL`、`CORS_ORIGINS`、`IMAGE_BASE_URL` 必须基于同一个 HTTPS 域名入口。

**可以保持默认的值：** 其他所有变量保持 `.env.production.example` 中的默认值即可。

### 3.3 上传并解压商品资产包

如果本次要初始化商品,请把鑫方盛商品批次资产包单独上传到服务器,解压到离线包目录的 `data/xfs/` 下:

```bash
cd /opt/buildlink-offline
mkdir -p data/xfs
tar xzf /path/to/xfs-output_xfs_20260623_023104.tar.gz -C data/xfs
```

解压后目录应类似:

```text
data/xfs/output_xfs_20260623_023104/
├── run.json
├── categories_raw.json
└── categories/
    └── .../offers/*/
        ├── offer.json
        └── images/*.jpg
```

### 3.3.1 配置 OpenResty / 1Panel 静态目录

如果使用宿主机 OpenResty / 1Panel 作为公网入口,请把 `/banners/` 指向离线包中的本地目录:

```text
/banners/  ->  /opt/buildlink-offline/data/banners/
```

同时保留反代规则:

```text
/        -> 127.0.0.1:3001
/api/    -> 127.0.0.1:8001
/static/ -> 127.0.0.1:8001
/healthz -> 127.0.0.1:8001
```

### 3.4 一键启动

```bash
bash deploy/deploy-offline.sh
```

脚本自动执行：加载镜像 → sha256 校验 → 启动三个容器 → 循环健康检查（最多 120s）

### 3.5 初始化数据（首次部署跑一次）

```bash
# 全量初始化（品类 + 商品）
bash deploy/init-data.sh --batch-dir data/xfs --yes

# 商品导入会先 dry-run 预检，确认后输入 y 正式导入
```

也可以分步跑：
```bash
bash deploy/init-data.sh --skip-products              # 只导品类
bash deploy/init-data.sh --skip-categories --batch data/xfs/<批次目录>  # 只导商品
```

### 3.6 浏览器验证

| 页面 | URL |
|------|-----|
| 前台首页 | `http://<IP>:3001` |
| 运营后台 | `http://<IP>:3001/zh/operator` |
| 健康检查 | `https://<域名>/healthz` |

---

## 四、后续更新

```bash
# 1. 打包机重新打包
bash deploy/package-offline.sh --api-url https://<域名> --tag 20260625

# 2. 传到服务器
scp buildlink-offline-20260625.tar.gz user@server:/opt/

# 3. 服务器上备份数据库
source .env.production
docker compose --env-file .env.production \
  exec -T db pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" \
  | gzip > /opt/backups/db-$(date +%Y%m%d_%H%M%S).sql.gz

# 4. 停旧服务
docker compose --env-file .env.production down

# 5. 解包新版本
cd /opt && tar xzf buildlink-offline-20260625.tar.gz && cd buildlink-offline

# 6. 复制旧配置 + 改 RELEASE_TAG
cp /opt/buildlink-offline-旧版/.env.production .env.production
sed -i 's/^RELEASE_TAG=.*/RELEASE_TAG=20260625/' .env.production

# 7. 启动
bash deploy/deploy-offline.sh

# 不需要重跑 init-data.sh（数据在 volume 里）
# 除非有新商品批次。新批次也建议作为独立资产包上传并解压:
# bash deploy/init-data.sh --skip-categories --batch data/xfs/<新批次>
```

---

## 五、常见问题

### Q: 换了服务器 IP 怎么办？
`API_BASE_URL` 是运行时注入的，修改 `.env.production` 后重启前端容器即可：`docker compose --env-file .env.production restart frontend`

### Q: 首页楼层背景图换了但页面还显示旧图？
楼层图 URL 支持运行时版本号。替换 `uploads/floors/*.webp` 后，把 `.env.production` 里的 `FLOOR_ASSET_VERSION` 改成日期或批次号，再重启前端容器即可，不需要重新 build 镜像。

### Q: 翻译不生效？
检查 `TRANSLATION_PROVIDER` 和对应的 API Key。在国内服务器上 Google Translate 不可用，需要用 `aliyun` 或 `mock`。

### Q: 数据库密码改了怎么办？
不能直接改 `.env.production`。需要先进容器改 PG 密码：
```bash
docker compose exec db psql -U 旧用户 -c "ALTER USER 旧用户 PASSWORD '新密码';"
```
然后再改 `.env.production`。

### Q: 怎么只导入新批次商品？
```bash
# 把新批次资产包解压到 data/xfs/ 下
bash deploy/init-data.sh --skip-categories --batch data/xfs/<新批次目录>
```

### Q: 怎么备份？
```bash
# 数据库
docker compose --env-file .env.production \
  exec -T db pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip > backup.sql.gz

# 图片（商品图+附件）
docker run --rm -v offline_platform_uploads:/data -v /opt/backups:/backup \
  alpine tar czf /backup/uploads-$(date +%Y%m%d).tar.gz -C /data .
```

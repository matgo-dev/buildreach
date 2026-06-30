# OpenResty 配置 (1Panel)

海外服务器 (162.19.98.142) 通过 1Panel 管理，使用 1Panel 自带的 OpenResty 做反向代理，不走 docker-compose 中的 nginx 服务。

## 架构

```
用户 → 1Panel OpenResty (80) → frontend (7857) / backend (17857)
```

- OpenResty 版本: 1.31.1.1-0-noble
- 容器名: 1Panel-openresty-bQg1

## 反向代理规则

在 1Panel → 网站 → 162.19.98.142 → 反向代理 中配置:

| 名称 | 路径 | 后端地址 | 浏览器缓存 |
|---|---|---|---|
| api | `/api/` | `http://127.0.0.1:17857` | 不缓存 |
| healthz | `/healthz` | `http://127.0.0.1:17857` | 不缓存 |
| root | `/` | `http://127.0.0.1:7857` | 不缓存 |
| static | `/static/` | `http://127.0.0.1:17857` | 365 天 + immutable |
| next-static | `/_next/static/` | `http://127.0.0.1:7857` | 365 天 |

### 缓存说明

- `/static/` — 商品图片，文件名含 uuid 内容不变，365 天 + immutable（二次访问零请求）
- `/_next/static/` — Next.js 打包的 JS/CSS，文件名带 content hash，部署新版本自动失效，365 天是业界标准

## 站点配置文件

在 1Panel → 网站 → 162.19.98.142 → 配置文件 中:

```nginx
server {
    listen 80 ;
    server_name 162.19.98.142;
    # gzip
    gzip on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript
               text/xml application/xml image/svg+xml;
    gzip_vary on;
    # max upload size
    client_max_body_size 100m;
    index index.php index.html index.htm default.php default.htm default.html;
    access_log /www/sites/162.19.98.142/log/access.log main;
    error_log /www/sites/162.19.98.142/log/error.log;
    location ~ ^/(\.user.ini|\.htaccess|\.git|\.env|\.svn|\.project|LICENSE|README.md) {
        return 404;
    }
    location ^~ /.well-known/acme-challenge {
        allow all;
        root /usr/share/nginx/html;
    }
    if ( $uri ~ "^/\.well-known/.*\.(php|jsp|py|js|css|lua|ts|go|zip|tar\.gz|rar|7z|sql|bak)$" ) {
        return 403;
    }
    root /www/sites/162.19.98.142/index;
    include /www/sites/162.19.98.142/proxy/*.conf;
}
```

### 手动添加项

- `gzip` — 压缩 HTML/CSS/JS/JSON，减少传输体积 60~80%
- `client_max_body_size 100m` — OpenResty 默认只允许 1MB 上传，调大到 100MB 支持图片/附件上传

## 待做

- [ ] 安全头 (X-Frame-Options, X-Content-Type-Options 等) — 由小陶统一配置
- [ ] `/images/` 缓存规则 — 前端 public 图片，优先级低，后续看需要
- [ ] 域名 matgo.ai DNS 解析 + HTTPS 证书
- [ ] 品类树 API 代理缓存 (proxy_cache) — 需要配 OpenResty cache path，后续优化

## 容器列表

| 容器名 | 镜像 | 端口 |
|---|---|---|
| buildlink-offline-frontend-1 | buildlink-frontend:TAG | 7857 → 3000 |
| buildlink-offline-backend-1 | buildlink-backend:TAG | 17857 → 8000 |
| buildlink-offline-db-1 | postgres:16.4-alpine | 内部 5432 |
| 1Panel-openresty-bQg1 | 1panel/openresty:1.31 | 80 |

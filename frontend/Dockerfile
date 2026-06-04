# ============================================================
# 央企海外工程供应链平台 · 前端镜像
# 多阶段构建:deps → builder → runner
# 用 pnpm + Next.js standalone 输出,生产模式启动(不要 dev / hot reload)
# ============================================================

# ============= deps =============
FROM node:20.18-alpine AS deps

# Alpine 镜像源换阿里云 + 淘宝 npm 镜像 + 锁定 pnpm 版本
# 严禁 pnpm@latest(昨天踩过 ERR_UNKNOWN_BUILTIN_MODULE)
RUN sed -i 's|https://dl-cdn.alpinelinux.org|https://mirrors.aliyun.com|g' /etc/apk/repositories \
    && npm config set registry https://registry.npmmirror.com \
    && corepack enable \
    && corepack prepare pnpm@9.15.0 --activate

WORKDIR /app
COPY package.json pnpm-lock.yaml ./

RUN pnpm config set registry https://registry.npmmirror.com \
    && pnpm install --frozen-lockfile

# ============= builder =============
FROM node:20.18-alpine AS builder

RUN sed -i 's|https://dl-cdn.alpinelinux.org|https://mirrors.aliyun.com|g' /etc/apk/repositories \
    && npm config set registry https://registry.npmmirror.com \
    && corepack enable \
    && corepack prepare pnpm@9.15.0 --activate

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* 是 client-side 变量,**必须 build 时注入**(打进 bundle)
# 运行时再改无效。compose 通过 build.args 传入。
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

RUN pnpm build

# ============= runner =============
FROM node:20.18-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production

# 非 root 用户(不装额外包,健康检查用 Node 自带 fetch)
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# Next.js standalone 输出:server.js + 最小 node_modules
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

ENV PORT=3000 \
    HOSTNAME=0.0.0.0

# 健康检查用 Node 自带 fetch(Node 18+ 内置),避免装 wget/curl
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD node -e "fetch('http://localhost:3000').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "server.js"]

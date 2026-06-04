import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Docker 部署:产出 standalone 自包含运行时(server.js + 最小 node_modules)
  // 镜像体积 / 启动速度 / 内存占用均优于 next start
  output: 'standalone',
};

export default withNextIntl(nextConfig);

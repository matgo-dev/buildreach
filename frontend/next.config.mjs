import { fileURLToPath } from "node:url";
import { dirname } from "node:path";
import createNextIntlPlugin from "next-intl/plugin";

// import.meta.dirname 要 Node ≥20.11,但 engines 允许 ≥20.10,低版本会得 undefined
// 令 outputFileTracingRoot 静默失效;用可移植写法,任意 Node 版本都拿得到本文件目录。
const projectRoot = dirname(fileURLToPath(import.meta.url));

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Docker 部署:产出 standalone 自包含运行时(server.js + 最小 node_modules)
  // 镜像体积 / 启动速度 / 内存占用均优于 next start
  output: 'standalone',
  // 钉死 file-tracing 根为本项目目录:Next 15 会因机器上存在其它 lockfile
  // 把 workspace root 推断到别处,导致 standalone 产物 tracing 错位。
  outputFileTracingRoot: projectRoot,
  // 全站商品图走后端 /static + 自生成缩略图,从不使用 next/image。
  // 关掉优化器后 /_next/image 不再做任何图片解码(sharp/libheif),
  // 这一类图片解析漏洞(如 GHSA-2xp9-vwfh-vxw4)的攻击面随之消失。
  images: { unoptimized: true },
};

export default withNextIntl(nextConfig);

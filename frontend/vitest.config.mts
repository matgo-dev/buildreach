import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// 只测纯逻辑 .ts(派生 / 计算),不测组件:组件的接线由联调与 tsc 守。
export default defineConfig({
  resolve: { alias: [{ find: /^@\//, replacement: fileURLToPath(new URL("./src/", import.meta.url)) }] },
  test: { include: ["src/**/*.test.ts"], environment: "node" },
});

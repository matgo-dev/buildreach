// 运行时环境变量占位 — 开发环境直接用，生产由 entrypoint.sh 覆写
window.__ENV = window.__ENV || { FLOOR_ASSET_VERSION: "" };

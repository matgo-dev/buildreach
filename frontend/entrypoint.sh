#!/bin/sh
# 容器启动时把环境变量注入 __env.js，让前端运行时读取。
# 用 node 生成 JSON 避免特殊字符转义问题。

ENV_FILE="/app/public/__env.js"

node -e "
  const env = {
    API_BASE_URL: process.env.API_BASE_URL || ''
  };
  const js = 'window.__ENV = ' + JSON.stringify(env) + ';';
  require('fs').writeFileSync('${ENV_FILE}', js);
  console.log('[entrypoint] __env.js ->', js);
"

exec node server.js

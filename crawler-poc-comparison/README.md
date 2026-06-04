# 柬埔寨双源对照 PoC

针对同一家柬埔寨公司、同一维度,**并排展示 Tavily+LLM 路径与自建爬虫路径的真实结果**,
为技术选型提供客观数据。覆盖两维度:工商基础、司法舆情。

## 调研定位

本 PoC 是一次可行性对比调研,评估两条数据获取路径在柬埔寨场景下的实际表现:
- **路径 A**:Tavily + LLM(公开网络搜索 + 大模型结构化抽取)
- **路径 B**:自建爬虫(直接抓取目标站点)

**范围**:国家=柬埔寨;维度=工商基础 + 司法舆情;不涉及资质认证、财务健康。

**路径独立**:两条路径在调用层完全独立、互不兜底,任一路径的成败仅代表该路径在该场景的表现。

**对照的本质**:两条路径召回的具体 URL 通常不同(Tavily 由其索引决定召回,爬虫由目标站点搜索引擎决定召回)。对比的是**两条路径整体的召回质量、覆盖完整度、运行特征**,不是字段级 1:1 对照。

## 与主项目的隔离声明

本 PoC 位于主项目 git 仓库下 `crawler-poc-comparison/` 独立目录,但与主项目**严格物理隔离**:

- 不 `import` 任何 `backend.*` / `frontend/*` 模块
- 不修改主项目任何文件
- 自带独立 `requirements.txt` / `.env` / `.gitignore`
- 端口 8004(避开主项目 8000/8003)

## 启动

```bash
cd crawler-poc-comparison
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # 填 TAVILY_API_KEY 和 QWEN_API_KEY
uvicorn main:app --reload --port 8004
```

访问:http://localhost:8004/

## API

```bash
curl -X POST http://localhost:8004/api/poc/compare \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Kampot Cement","force_refresh":false}'
```

## 测试公司

覆盖不同企业规模(规模差异会影响 Tavily / 爬虫两条路径的表现):1-2 家大企业 + 2-3 家中小企业。

| 公司名 | 规模 | MOC 注册号 | 测试要点 |
|---|---|---|---|
| `Kampot Cement` | 大企业 | (无) | 媒体覆盖高,司法舆情演示效果好 |
| `Acleda Bank` | 大企业 | (无) | 大银行,媒体覆盖极高 |
| `KHALIBRE CO.,LTD` | 中小企业 | 00002730 | 中小企业,GLEIF 有 LEI 记录 |
| `T.S SPORT (CAMBODIA) CO., LTD.` | 中小企业 | 00052477 | 中小企业 |
| `TOP FORM (CAMBODIA) COMPANY LIMITED` | 中小企业 | 00015130 | 中小企业 |

## 已知限制

- Tavily 侧 24h 文件缓存(`.cache/`);爬虫侧每次实时
- 不做反幻觉(诚实展示 LLM 原始抽取效果)
- 不做反爬对抗、不引入 Playwright;爬虫被反爬(403/登录/JS)即记录,不绕过
- 仅英文媒体,不处理柬语
- 跑测结果与判断见 `reports/poc_report.md`

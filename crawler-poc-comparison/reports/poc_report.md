# 柬埔寨双源对比调研报告

> 跑测日期:2026-05-26
> 环境:本地,Tavily Search + qwen-plus 裸调 / httpx + BeautifulSoup 爬虫(无浏览器、无反爬对抗)
> 测试公司:Kampot Cement、KHALIBRE CO.,LTD、Acleda Bank

## 1. 调研背景与范围

对比两条数据获取路径在柬埔寨场景下的实际表现:
- **路径 A**:Tavily + LLM(公开网络搜索 + qwen-plus 结构化抽取)
- **路径 B**:自建爬虫(MOC 官网 / 媒体站直抓)

覆盖维度:工商基础(7 字段)+ 司法舆情。两路调用层独立、互不兜底。

## 2. 跑测结果汇总

| 测试公司 | 维度 | 路径 A(Tavily+LLM) | 路径 B(爬虫) | A 耗时 |
|---|---|---|---|---|
| Kampot Cement | 工商基础 | ok · 2/7 字段 | access_restricted(MOC 403) | 4.5s |
| Kampot Cement | 司法舆情 | ok · 2 篇 / 2 负面 | access_restricted(媒体 403) | 9.6s |
| KHALIBRE CO.,LTD | 工商基础 | ok · 1/7 字段 | access_restricted | 2.8s |
| KHALIBRE CO.,LTD | 司法舆情 | no_match · 0 篇 | access_restricted | 2.3s |
| Acleda Bank | 工商基础 | ok · 3/7 字段(含注册号 00003077) | access_restricted | 3.7s |
| Acleda Bank | 司法舆情 | no_match · 0 篇 | access_restricted | 1.5s |

## 3. 工商基础维度

### 3.1 路径 A:Tavily + LLM 观察
- 调用结果:三家均 ok。
- 字段填充:1~3 / 7;稳定拿到 `company_full_name`、`country_region`,大企业(Acleda)能拿 `registration_no`。
- 数据来源:OpenDevelopment Mekong、OpenCorporates 镜像等公开聚合站。
- 运行特征:单次 2.8~4.5s,`search_depth=basic` 摘要短是填充率偏低主因。

### 3.2 路径 B:自建爬虫(降级链)观察

v1.2 工商爬虫升级为 4 级降级链:**MOC → OpenCorporates → Wikipedia → GLEIF API,命中即停**。

#### 3.2.1 降级链各源实测表现(5 家公司,按规模)

> 命中即停:大企业在第 3 级 Wikipedia 命中后不再走 GLEIF,故 GLEIF 仅对 3 家中小企业触发。

| 源 | 触发次数 | ok | access_restricted | no_match | 说明 |
|---|---|---|---|---|---|
| moc.gov.kh | 5 | 0 | 5 | 0 | 全 HTTP 403,首请求即拒 |
| opencorporates.com | 5 | 0 | 5 | 0 | HAProxy + hCaptcha 挑战页(HTTP 200 但实为 captcha 页),httpx 抓不过,需浏览器执行 JS |
| en.wikipedia.org | 5 | 2 | 0 | 3 | REST API:大企业(ACLEDA/Kampot)有词条命中;中小企业 404 无词条 |
| api.gleif.org | 3 | 0 | 0 | 3 | 仅中小企业触发;模糊匹配返回 F.U.G.I GOLD,经命中校验拒绝,无真命中 |

#### 3.2.2 降级链整体效果

- 整体命中率:**2/5** —— 大企业 **2/2**(均在第 3 级 Wikipedia 命中),中小企业 **0/3**(无词条 + GLEIF 无真命中)
- 命中层级:第 3 级(Wikipedia REST summary API)
- 字段填充(命中时):Wikipedia summary 仅 **2/7**(企业全称 + 国别),无注册号/成立日期/法人(summary 不含 infobox)
- 规模差异显著:**企业越大、越知名,公开数据源覆盖越好**;中小企业在所有公开源都查不到

#### 3.2.3 各源字段覆盖能力(实测)

| 字段 | moc | opencorp | wiki(REST) | gleif |
|---|---|---|---|---|
| company_full_name | (403) | (未解析) | ✓(有词条时) | (无真命中) |
| country_region | — | — | ✓ | — |
| registration_no / 成立日期 / 其他 | — | — | ✗(summary 无 infobox) | — |

实测中只有 Wikipedia(大企业)真正产出字段,且仅 2/7。

#### 3.2.4 站点访问特征

- `moc.gov.kh`:HTTP 403,WAF / 需登录,纯爬不可行
- `opencorporates.com`(URL/DOM 已按真实结构修正,定位非问题所在):
  - **访问特征**:站点用 **HAProxy + hCaptcha** 挑战页拦截非浏览器客户端 —— 返回 HTTP 200,但 body 仅 ~1.5KB,内容是 `<title>HAProxy Challenge</title>` + `js.hcaptcha.com` 验证框,非真实结果页
  - **浏览器 vs 纯 HTTP 客户端**:同一 URL 浏览器实测可正常返回结果;httpx / 任何纯 HTTP 客户端(无 JS 执行、非真实 Chrome 指纹)被挑战页拦截。实测带不带 `cookie_consent=accepted` 返回字节完全一致 —— 与 cookie consent 无关
  - **绕过成本**:需 Playwright + 真实浏览器指纹执行 JS,或接入打码平台过 hCaptcha
  - **本 PoC 结论**:不引入这类重型工具,如实记录为 `access_restricted`(诚实标注"被挑战页拦",非误报"搜不到")
- `en.wikipedia.org`:REST summary API 可用,但须遵守 Wikimedia UA 策略(UA 带 URL+email 联系方式),否则 403;仅大企业有词条
- `api.gleif.org`:REST JSON 可调,但 `filter[legalName]` 是模糊匹配会返回不相关公司,**必须做命中校验**;柬埔寨中小企业基本无 LEI 记录

#### 3.2.5 两个关键校验教训(v1.2 修复)

- **Wikipedia 403 ≠ 反爬不可破**:是 UA 不合规;换合规 UA 即通。盲目归因"被封"会漏掉可用源。
- **GLEIF 命中必须验名**:模糊搜索源返回"沾边"结果,直接采信会张冠李戴(查 T.S SPORT 命中 F.U.G.I GOLD)。**凡模糊匹配源,命中后都要校验返回主体 == 查询主体**。

### 3.3 两条路径对比

- **字段覆盖**:Tavily+LLM 1~3/7(全称/国别/注册号);爬虫降级链 2/5 公司命中(均为大企业、靠 Wikipedia),命中也只 2/7、无注册号。
- **数据形态**:Tavily 走网页摘要 → LLM 归纳;爬虫降级链中只有 REST 类源(Wikipedia summary / GLEIF JSON)能结构化产出,HTML 类源(MOC/OpenCorp)全军覆没。
- **规模敏感**:爬虫降级链对**大企业**有效(Wikipedia 有词条),对**中小企业**几乎无效(公开源无收录);Tavily+LLM 受规模影响相对小。
- **适用场景**:工商基础**仍以 Tavily+LLM 为主**;Wikipedia/GLEIF 作为"知名大企业"的结构化补充源(且都需命中校验);HTML 爬虫(MOC/OpenCorp)在柬埔寨不可行。

## 4. 司法舆情维度

### 4.1 路径 A:Tavily + LLM 观察
- Kampot Cement 召回 2 篇且判负面;KHALIBRE / Acleda 召回 0(no_match)。
- 召回量与公司公开报道量强相关。

### 4.2 路径 B:自建爬虫(媒体站)观察
- phnompenhpost.com + khmertimeskh.com 均 access_restricted(Cloudflare JS challenge,HTTP 403)。
- 三家公司、两站均未取得任何内容。

### 4.3 召回内容对比(以 Kampot Cement 为例)
| 项 | 数量 |
|---|---|
| Tavily + LLM 召回 | 2 |
| 爬虫召回 | 0 |
| 两边同时召回 | 0 |
| 仅 Tavily + LLM 召回 | 2 |
| 仅爬虫召回 | 0 |

对比解读:重合度 0/(2+0-0) = 0% → 两条路径内容无重合,但**原因是路径 B 完全无召回**(被反爬挡),并非内容互补。当前无法做有意义的重合度对照,因为爬虫侧无数据。

### 4.4 两条路径对比
- 路径 A 是司法舆情唯一能产出数据的路径;路径 B 被 Cloudflare 完全挡死。

## 5. 调研结论与后续建议

### 5.1 数据观察
- 三个目标站(MOC + 两媒体)共 6 次爬虫调用全部 access_restricted(403)。
- Tavily+LLM 两维度均能调通,工商填充 1~3/7,司法召回与知名度相关。

### 5.2 后续路径选项

**选项 1:以 Tavily + LLM 为主路径**
- 适用条件:目标站点普遍有反爬,公开网络有一定覆盖。
- 待解决:工商填充率偏低(1~3/7),需 `advanced` depth / 补结构化源。

**选项 2:以爬虫为主路径**
- 适用条件:目标站点无反爬、有稳定结构化页面。
- 待解决:本场景三站全 403,需浏览器渲染 / 授权,成本高、合规存疑 —— 本期判定不适用。

**选项 3:两条路径组合(Tavily 主 + 爬虫补特定可爬源)**
- 组合方式:Tavily 兜底全量,对个别无反爬的权威源补爬虫。
- 待解决:柬埔寨暂未发现可稳定爬取的权威结构化源。

**选项 4:其他路径**
- 商业工商数据 API(OpenCorporates 付费)、官方 RSS、用户上传 + OCR 补全。

### 5.3 推荐

基于本次调研数据,推荐 **选项 1(Tavily + LLM 为主路径)**,并以选项 4 的"用户上传补全"补工商关键字段。

理由:
- 爬虫路径在柬埔寨三站全部 403,当前调用方式不可用。
- Tavily + LLM 是唯一稳定产出数据的路径,与主项目 Δ7 主线一致。

### 5.4 待进一步验证
- `search_depth=advanced` 能否显著提升工商填充率。
- 司法召回随 `max_results` / 多 query 的提升空间。
- 其他国别(非柬埔寨)目标站是否也普遍反爬。

## 6. 四维度 × 数据源性质分析(柬埔寨)

### 6.1 核心判断:爬虫能否独立出字段,取决于数据源是否结构化

爬虫只负责"取数据",**能否直接得到评分字段,取决于源本身**:

- **结构化源**(官方数据库、有固定字段的表格页):爬虫可直接抽出字段,**不需要 LLM**。
- **非结构化源**(新闻、网页正文):爬虫只能取到文本,字段(如负面等级、诉讼数)**必须靠 LLM 语义归纳**(或人工)。

也就是说,"爬虫"和"大模型"是两件事:爬虫负责**取文本**,大模型负责**出字段**。源越非结构化,越离不开 LLM。

### 6.2 四维度在柬埔寨的实际情况

| 维度 | 字段性质 | 柬埔寨可得数据源 | 源是否结构化 | 出字段是否需 LLM | 爬虫能否独立 |
|---|---|---|---|---|---|
| 工商基础 | 结构化(注册号/日期/法人) | MOC 官网(结构化,但实测 403)、OpenCorporates 镜像(半结构网页) | 部分 | MOC 若可爬→否;走网页/Tavily→需 | 理论可,**实测 MOC 403 不可行** |
| 资质认证 | 半结构(是否持证) | ISO 目录、ISC(mpwt.gov.kh) | 认证目录结构化,但"某公司是否持证"散在网页 | 多数需 LLM 判断归属 | 部分(目录可查),绑定到公司难 |
| 财务健康 | 结构化(营收/负债率) | 上市:CSX 财报;**私企:无公开数据** | 上市结构化 | 上市可爬财报→否 | 上市可独立,**私企无源**(柬埔寨以私企为主→大面积缺失) |
| 司法舆情 | 非结构(负面等级/诉讼数/失信) | **无公开结构化司法库**;仅新闻媒体(非结构 + 反爬) | 否 | **必须 LLM 归纳** | **不能**(非结构 + 反爬 + 需语义归纳,三重制约) |

### 6.3 结论

- **司法舆情**:柬埔寨没有公开的结构化司法数据库(法院判决 / 失信名单不开放),能拿的只有**新闻媒体(非结构化)**,且媒体站被 Cloudflare 反爬。字段(`negative_news_level` / `litigation_count` 等)**必须靠 LLM 从文章归纳,爬虫单独做不到** —— 这是四维度里对爬虫最不利的,也印证了主项目 Δ7 司法维度走 Tavily+LLM 的设计。
- **工商基础**:字段本是结构化,理论上 MOC 官网可直接爬出、不需 LLM;但实测 MOC 403 反爬,只能退到 Tavily+LLM(网页文本→LLM 归纳,填充率 1~3/7)。
- **财务健康**:上市企业财报结构化(可爬/可 API),但柬埔寨绝大多数供应商是私企、财务不公开 —— **大面积无源**,任何方法都难,需靠用户上传补全。
- **资质认证**:认证目录(ISO/ISC)结构化可查,但"某公司是否持有某证"通常要从网页/公告里判断归属,仍依赖 LLM 或人工。

**整体**:柬埔寨四维度中,**只有"工商基础(若 MOC 可爬)"理论上爬虫能独立产出字段**,但实测反爬使其也不可行;其余三维度本质依赖 LLM 归纳或根本无公开源。**因此柬埔寨场景下四维度统一走 Tavily+LLM 更现实,司法舆情尤其不能单靠爬虫。**

## 附录

### A. 重合 URL 完整清单
当前爬虫侧 0 召回,无重合 URL。Tavily 侧召回 URL 见前端"召回内容对比"点击展开。

### B. 各路径调用特征
- Tavily+LLM:每公司每维度 1 次搜索 + 1 次 LLM 抽取,24h 文件缓存。
- 爬虫:每次实时,均 403 快速失败。

### C. 测试公司原始返回
见前端页面底部"完整调用元信息(ComparisonResponse JSON)"展开。

---

*v1.1 调研报告。核心结论:柬埔寨场景爬虫路径三站全 403 不可用,Tavily+LLM 是唯一可行路径,印证主项目 Δ7 主线。*

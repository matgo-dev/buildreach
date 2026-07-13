/**
 * AI 智能体 Mock 数据 — 预设对话脚本 + 关键词匹配
 */

type L10n = { zh: string; en: string; sw: string };

export interface AgentDef {
  id: string;
  icon: string;
  color: string;        // tailwind bg class
  accentHex: string;    // 按钮/高亮色
  /** 多语言 greeting — 运行时按 locale 取 */
  greeting: string;
  greetingL10n: L10n;
  suggestions: string[];
  suggestionsL10n: { zh: string[]; en: string[]; sw: string[] };
  qa: { keywords: string[]; answer: string }[];
  fallback: string;
  fallbackL10n: L10n;
}

/** 根据 locale 获取 greeting */
export function getGreeting(agent: AgentDef, locale: string): string {
  return agent.greetingL10n[locale as keyof L10n] ?? agent.greeting;
}
/** 根据 locale 获取 suggestions */
export function getSuggestions(agent: AgentDef, locale: string): string[] {
  return agent.suggestionsL10n[locale as keyof L10n] ?? agent.suggestions;
}
/** 根据 locale 获取 fallback */
export function getFallback(agent: AgentDef, locale: string): string {
  return agent.fallbackL10n[locale as keyof L10n] ?? agent.fallback;
}
/** 匹配答案，无匹配时用 locale 对应的 fallback */
export function matchAnswer(agent: AgentDef, input: string, locale?: string): string {
  const text = input.toLowerCase();
  let best: { score: number; answer: string } | null = null;
  for (const qa of agent.qa) {
    const score = qa.keywords.filter((kw) => text.includes(kw.toLowerCase())).length;
    if (score > 0 && (!best || score > best.score)) {
      best = { score, answer: qa.answer };
    }
  }
  return best?.answer ?? getFallback(agent, locale ?? "zh");
}

// ─── 拼柜计算助手 ──────────────────────────────────
const containerAgent: AgentDef = {
  id: "container",
  icon: "📦",
  color: "bg-blue-50",
  accentHex: "#10b981",
  greeting: "你好！我是 Matgo 筑达 智能拼柜助手 🚢\n\n我可以帮你：\n• 根据货物信息推荐最优柜型\n• 计算装载率和运费估算\n• 对比整柜 vs 拼柜方案\n\n请告诉我你的货物信息，或点击下方快捷问题开始体验。",
  greetingL10n: {
    zh: "你好！我是 Matgo 筑达 智能拼柜助手 🚢\n\n我可以帮你：\n• 根据货物信息推荐最优柜型\n• 计算装载率和运费估算\n• 对比整柜 vs 拼柜方案\n\n请告诉我你的货物信息，或点击下方快捷问题开始体验。",
    en: "Hello! I'm Matgo Container Loading Assistant 🚢\n\nI can help you:\n• Recommend optimal container types based on cargo info\n• Calculate loading rates and freight estimates\n• Compare FCL vs LCL options\n\nTell me about your cargo, or tap a quick question below.",
    sw: "Habari! Mimi ni Msaidizi wa Kupakia Kontena wa Matgo 🚢\n\nNinaweza kukusaidia:\n• Kupendekeza aina bora ya kontena\n• Kukokotoa kiwango cha upakiaji na makadirio ya nauli\n• Kulinganisha FCL na LCL\n\nNiambie kuhusu mizigo yako, au bonyeza swali hapo chini.",
  },
  suggestions: ["我有 500 箱瓷砖要发蒙巴萨", "20GP 和 40HQ 有什么区别？", "帮我计算拼柜费用"],
  suggestionsL10n: {
    zh: ["我有 500 箱瓷砖要发蒙巴萨", "20GP 和 40HQ 有什么区别？", "帮我计算拼柜费用"],
    en: ["I have 500 boxes of tiles to Mombasa", "What's the difference between 20GP and 40HQ?", "Calculate LCL costs for me"],
    sw: ["Nina masanduku 500 ya vigae kwenda Mombasa", "Tofauti kati ya 20GP na 40HQ?", "Kokotoa gharama za LCL"],
  },
  qa: [
    {
      keywords: ["瓷砖", "蒙巴萨", "500"],
      answer: `好的，为您分析 500 箱瓷砖发往蒙巴萨的方案：

📊 **货物信息**
| 项目 | 数值 |
|------|------|
| 品类 | 瓷砖（600×600mm） |
| 数量 | 500 箱 |
| 单箱尺寸 | 64×64×8 cm |
| 单箱重量 | 32 kg |
| 总体积 | 16.4 CBM |
| 总重量 | 16,000 kg |

📦 **推荐方案：1×20GP 整柜**
| 指标 | 数值 |
|------|------|
| 柜型 | 20GP（容积 33 CBM / 限重 21.8T） |
| 装载率 | 49.7%（体积）/ 73.4%（重量） |
| 海运费（宁波→蒙巴萨） | $1,850 - $2,200 |
| 预计船期 | 22-28 天 |

💡 **建议**：瓷砖属于重货，20GP 重量利用率已达 73%，是最经济的选择。如果凑到 800+ 箱，可以考虑 40HQ 降低单箱运费。

需要我帮您估算清关和本地配送费用吗？`,
    },
    {
      keywords: ["20GP", "40HQ", "区别", "对比"],
      answer: `好的，为您对比常见柜型：

📦 **集装箱柜型对比**
| 柜型 | 内部尺寸（长×宽×高） | 容积 | 限重 | 适用场景 |
|------|---------------------|------|------|---------|
| 20GP | 5.9m × 2.35m × 2.39m | 33 CBM | 21.8T | 重货（瓷砖、钢材） |
| 40GP | 12.0m × 2.35m × 2.39m | 67 CBM | 26.5T | 大件标准货 |
| 40HQ | 12.0m × 2.35m × 2.69m | 76 CBM | 26.5T | 轻泡货（家具、管材） |

💰 **运费参考（中国→东非）**
| 柜型 | 运费范围 | 单 CBM 成本 |
|------|---------|------------|
| 20GP | $1,800 - $2,500 | $55-76/CBM |
| 40GP | $2,800 - $3,600 | $42-54/CBM |
| 40HQ | $3,000 - $3,800 | $39-50/CBM |

💡 **选柜建议**：
- 体积 < 25 CBM → 选 **20GP**
- 体积 25-55 CBM → 选 **40GP**
- 体积 > 55 CBM 或货物超高 → 选 **40HQ**
- 货物超重超体积 → 考虑 **拼柜 LCL**

需要我根据您的具体货物推荐柜型吗？`,
    },
    {
      keywords: ["拼柜", "LCL", "费用", "计算"],
      answer: `好的，为您介绍拼柜（LCL）费用构成：

🔢 **拼柜费用计算公式**
\`\`\`
总费用 = 海运费 + 码头费 + 文件费 + 目的港杂费
\`\`\`

💰 **各项费用明细（中国→达累斯萨拉姆）**
| 费用项 | 计费方式 | 参考价格 |
|--------|---------|---------|
| 海运费 | 按 CBM 或吨（取大） | $65-85/CBM |
| 起运港杂费 | 按票 | $150-200/票 |
| 文件费 | 按票 | $80-120/票 |
| 目的港杂费 | 按 CBM | $25-35/CBM |
| 清关代理费 | 按票 | $100-150/票 |

📊 **示例：5 CBM 建材拼柜**
| 项目 | 金额 |
|------|------|
| 海运费 | $75 × 5 = $375 |
| 起运港杂费 | $180 |
| 文件费 | $100 |
| 目的港杂费 | $30 × 5 = $150 |
| **合计** | **$805** |

💡 **拼柜 vs 整柜建议**：
- < 15 CBM → 拼柜更划算
- 15-25 CBM → 接近临界点，需单独比价
- > 25 CBM → 整柜 20GP 更经济

需要我根据您的货量做精确对比吗？`,
    },
    {
      keywords: ["钢材", "钢管", "钢筋"],
      answer: `好的，钢材类产品的拼柜方案比较特殊，为您分析：

⚠️ **钢材运输注意事项**
- 钢材属于 **超重货**，通常限重先于限体积
- 20GP 限重 21.8T，实际装载约 18-20T（预留安全余量）
- 需要特别注意 **绑扎加固**，费用另计

📦 **常见钢材装柜参考**
| 品类 | 20GP 可装量 | 40GP 可装量 |
|------|-----------|-----------|
| 螺纹钢 Ø12 | 20-22 吨 | 26-28 吨 |
| 方管 50×50 | 18-20 吨 | 25-26 吨 |
| 彩钢瓦 0.4mm | 12-15 吨 | 22-25 吨 |
| 角钢 50×50 | 20-22 吨 | 26-28 吨 |

💰 **运费参考（中国→东非）**
钢材因重量大，通常按 **W/M（重量吨或体积取大）** 计费，
单吨海运费约 $90-130/吨（20GP 整柜摊薄后）。

需要我根据具体钢材规格计算装载方案吗？`,
    },
    {
      keywords: ["家具", "门", "窗"],
      answer: `好的，家具/门窗属于 **轻泡货**，拼柜策略和重货完全不同：

📦 **推荐柜型：40HQ**
家具/门窗体积大但重量轻，40HQ 多出的 30cm 高度非常关键。

📊 **常见家具装柜参考**
| 品类 | 40HQ 可装量 | 装载率 |
|------|-----------|--------|
| 木门（标准） | 180-220 樘 | 85-92% |
| 铝合金窗 | 120-150 ㎡ | 80-88% |
| 办公桌椅 | 60-80 套 | 75-85% |
| 厨柜 | 8-12 套 | 80-90% |

💡 **轻泡货省钱技巧**：
1. **拆装打包**：家具拆散打平板包装可提升 30-50% 装载率
2. **混装填缝**：大件之间塞入五金配件、小件建材
3. **拼柜组合**：和重货（如瓷砖）混拼，重量+体积互补最经济

需要我帮您计算具体的装载方案吗？`,
    },
  ],
  fallback: "感谢您的提问！我目前能处理柜型选择、装载率计算、运费估算等常见问题。\n\n如果您有更复杂的需求，我们的物流顾问可以为您提供专业方案。请通过页面右下角的 WhatsApp 联系我们 💬",
  fallbackL10n: {
    zh: "感谢您的提问！我目前能处理柜型选择、装载率计算、运费估算等常见问题。\n\n如果您有更复杂的需求，我们的物流顾问可以为您提供专业方案。请通过页面右下角的 WhatsApp 联系我们 💬",
    en: "Thanks for your question! I currently handle container selection, loading rate calculation, and freight estimates.\n\nFor more complex needs, our logistics team can provide a tailored solution. Contact us via WhatsApp 💬",
    sw: "Asante kwa swali lako! Kwa sasa ninashughulikia uchaguzi wa kontena, kukokotoa kiwango cha upakiaji, na makadirio ya nauli.\n\nKwa mahitaji zaidi, timu yetu ya usafirishaji inaweza kusaidia. Wasiliana nasi kupitia WhatsApp 💬",
  },
};

// ─── 合规资质顾问 ──────────────────────────────────
const complianceAgent: AgentDef = {
  id: "compliance",
  icon: "📋",
  color: "bg-[#fdf4dc]",
  accentHex: "#c1850b",
  greeting: "你好！我是 Matgo 筑达 合规资质顾问 📋\n\n我可以帮你：\n• 查询目的国所需的产品认证和资质\n• 了解 PVOC / COC / SONCAP 等合规要求\n• 获取认证费用、周期和办理流程\n\n请告诉我您要出口的品类和目的国，或点击下方快捷问题。",
  greetingL10n: {
    zh: "你好！我是 Matgo 筑达 合规资质顾问 📋\n\n我可以帮你：\n• 查询目的国所需的产品认证和资质\n• 了解 PVOC / COC / SONCAP 等合规要求\n• 获取认证费用、周期和办理流程\n\n请告诉我您要出口的品类和目的国，或点击下方快捷问题。",
    en: "Hello! I'm Matgo Compliance Advisor 📋\n\nI can help you:\n• Look up required certifications for your destination country\n• Understand PVOC / COC / SONCAP requirements\n• Get certification costs, timelines and processes\n\nTell me the product category and destination, or tap a quick question.",
    sw: "Habari! Mimi ni Mshauri wa Uzingatiaji wa Matgo 📋\n\nNinaweza kukusaidia:\n• Kutafuta vyeti vinavyohitajika kwa nchi lengwa\n• Kuelewa mahitaji ya PVOC / COC / SONCAP\n• Kupata gharama, muda na mchakato wa uthibitisho\n\nNiambie aina ya bidhaa na nchi lengwa, au bonyeza swali hapo chini.",
  },
  suggestions: ["瓷砖出口肯尼亚需要什么认证？", "PVOC 是什么？怎么办理？", "坦桑尼亚的建材进口政策"],
  suggestionsL10n: {
    zh: ["瓷砖出口肯尼亚需要什么认证？", "PVOC 是什么？怎么办理？", "坦桑尼亚的建材进口政策"],
    en: ["What certifications for tiles to Kenya?", "What is PVOC and how to apply?", "Tanzania building materials import policy"],
    sw: ["Vyeti gani kwa vigae kwenda Kenya?", "PVOC ni nini na jinsi ya kuomba?", "Sera ya kuagiza vifaa vya ujenzi Tanzania"],
  },
  qa: [
    {
      keywords: ["肯尼亚", "瓷砖", "认证"],
      answer: `好的，为您查询瓷砖出口肯尼亚的合规要求：

🇰🇪 **肯尼亚 — 瓷砖进口认证要求**

📋 **必须认证**
| 认证 | 全称 | 说明 |
|------|------|------|
| **PVOC** | Pre-Export Verification of Conformity | 装船前检验，所有进口商品必须 |
| **COC** | Certificate of Conformity | 符合性证书，PVOC 通过后签发 |
| **IDF** | Import Declaration Form | 进口申报表，进口商在肯尼亚申请 |

📝 **PVOC 办理流程**
1. 提交申请（产品资料 + 测试报告 + 装箱单 + 发票）
2. 检验机构验货（SGS / Bureau Veritas / Intertek）
3. 抽样测试（如需要）
4. 签发 COC 证书
5. 出口清关使用

💰 **费用 & 周期**
| 项目 | 参考价格 | 周期 |
|------|---------|------|
| PVOC 检验费 | FOB 金额的 0.5-0.6%（最低 $280） | 3-5 个工作日 |
| 产品测试费（如需） | $200-500 | 5-7 个工作日 |
| 加急服务 | +50% 费用 | 1-2 个工作日 |

⚠️ **注意事项**
- 瓷砖需符合 **KS 02-508** 肯尼亚标准
- 需提供放射性检测报告
- 每批次单独申请，不可混批

需要我帮您查询其他国家的要求吗？`,
    },
    {
      keywords: ["PVOC", "是什么", "办理"],
      answer: `好的，为您详细介绍 PVOC：

📋 **PVOC（Pre-Export Verification of Conformity）**
装船前符合性验证计划，是部分非洲国家的强制性进口检验制度。

🌍 **实施 PVOC 的国家**
| 国家 | 实施时间 | 检验机构 |
|------|---------|---------|
| 🇰🇪 肯尼亚 | 2005 年 | SGS, BV, Intertek |
| 🇹🇿 坦桑尼亚 | 2012 年 | SGS, BV |
| 🇺🇬 乌干达 | 2010 年 | SGS, BV, Intertek |
| 🇷🇼 卢旺达 | 2016 年 | SGS |
| 🇪🇹 埃塞俄比亚 | 2013 年 | BV, CIQTEK |

📝 **办理步骤**
1. **准备资料**：形式发票、装箱单、产品测试报告、IDF（进口商提供）
2. **提交申请**：向指定检验机构提交 RFC（Request for Conformity）
3. **现场验货**：检验员到工厂/仓库验货（核对品名、数量、标识）
4. **签发 COC**：验货通过后 1-3 天签发 Certificate of Conformity
5. **使用 COC**：出口报关 + 目的港清关必备文件

💰 **费用结构**
\`\`\`
总费用 = 检验费（FOB × 0.5%）+ 测试费（如需）+ 差旅费（如异地验货）
最低收费：$250-300/票
\`\`\`

⚠️ **常见坑**
- 没有 COC，货到港后会被 **扣关 + 罚款**
- COC 有效期通常为 **发货后 90 天**
- 部分产品需要 **型式测试报告**（首次出口时做一次即可）

需要我帮您评估具体产品的 PVOC 要求吗？`,
    },
    {
      keywords: ["坦桑尼亚", "建材", "政策", "进口"],
      answer: `好的，为您整理坦桑尼亚建材进口政策：

🇹🇿 **坦桑尼亚 — 建材进口合规指南**

📋 **必须认证**
| 认证 | 说明 | 适用 |
|------|------|------|
| **PVOC-COC** | 装船前检验证书 | 所有进口商品 |
| **TBS 标准** | 坦桑尼亚标准局认证 | 水泥、钢材、电线等 |
| **TFDA** | 食品药品局许可 | 涉及化学品的建材（如防水涂料） |

📦 **常见建材关税税率**
| 品类 | 进口关税 | 增值税 | 总税负 |
|------|---------|--------|--------|
| 瓷砖 | 25% | 18% | ~48% |
| 水泥 | 25% | 18% | ~48% |
| 钢材 | 10% | 18% | ~30% |
| PVC 管 | 25% | 18% | ~48% |
| 电线电缆 | 10% | 18% | ~30% |
| 铝型材 | 10% | 18% | ~30% |

⚠️ **特别注意**
1. **水泥** — 坦桑尼亚对进口水泥实施 **反倾销税**，需提前确认
2. **钢材** — 需符合 **TZS 161** 标准，需提交厂检报告
3. **二手设备** — 超过 **10 年** 的二手建筑设备 **禁止进口**
4. **木材** — 需 **植物检疫证书 + 熏蒸证明**

📍 **清关港口**
| 港口 | 清关时间 | 备注 |
|------|---------|------|
| 达累斯萨拉姆 | 5-10 天 | 主要港口，量大 |
| 桑给巴尔 | 3-5 天 | 小批量 |

需要我帮您查询其他品类或国家的政策吗？`,
    },
    {
      keywords: ["SONCAP", "尼日利亚"],
      answer: `好的，为您介绍尼日利亚 SONCAP 认证：

🇳🇬 **SONCAP（Standards Organization of Nigeria Conformity Assessment Programme）**

📋 **认证结构（三证体系）**
| 证书 | 全称 | 申请方 | 有效期 |
|------|------|--------|--------|
| **PC** | Product Certificate | 出口商 | 1-3 年 |
| **SC** | SONCAP Certificate | 进口商 | 单批次 |
| **COC** | Certificate of Conformity | 检验机构签发 | 单批次 |

📝 **办理流程**
1. 出口商向检验机构申请 **PC**（产品证书）
2. 提交：产品测试报告 + 工厂质量体系文件
3. 进口商在尼日利亚申请 **Form M**
4. 装船前验货 → 签发 **COC**
5. 进口商凭 COC 换取 **SC** → 清关

💰 **费用参考**
| 项目 | 费用 | 说明 |
|------|------|------|
| PC 申请 | $1,500-3,000 | 含测试费，首次较贵 |
| 每批次 COC | FOB × 0.45% | 最低 $300 |
| SC 换证 | ≈ $150-200 | 进口商在尼日利亚支付 |

⚠️ **建材出口尼日利亚注意**
- 瓷砖、钢材、水泥均属 **管控清单**，必须 SONCAP
- PC 有效期内可多次出货，申请一次即可复用
- 没有 SONCAP 的货物将被 **拒绝清关或退运**

需要了解其他非洲国家的认证要求吗？`,
    },
    {
      keywords: ["清单", "哪些国家", "非洲", "认证"],
      answer: `好的，为您整理非洲主要市场的建材进口认证清单：

🌍 **非洲主要市场认证要求一览**

| 国家 | 认证制度 | 检验机构 | 建材关税 | 难度 |
|------|---------|---------|---------|------|
| 🇰🇪 肯尼亚 | PVOC | SGS/BV/Intertek | 25% | ⭐⭐ |
| 🇹🇿 坦桑尼亚 | PVOC + TBS | SGS/BV | 10-25% | ⭐⭐⭐ |
| 🇺🇬 乌干达 | PVOC | SGS/BV/Intertek | 10-25% | ⭐⭐ |
| 🇳🇬 尼日利亚 | SONCAP | SGS/BV/Intertek | 10-35% | ⭐⭐⭐⭐ |
| 🇬🇭 加纳 | SOA | GSA | 10-20% | ⭐⭐ |
| 🇪🇹 埃塞俄比亚 | ECAE | BV/CIQTEK | 10-35% | ⭐⭐⭐ |
| 🇿🇦 南非 | NRCS/LOA | SABS | 0-15% | ⭐⭐⭐⭐ |
| 🇪🇬 埃及 | GOEIC | 当地机构 | 5-40% | ⭐⭐⭐ |

💡 **建议**：
- 首次出口建议选 **肯尼亚/乌干达**（流程简单、中国检验机构覆盖好）
- 尼日利亚市场大但流程复杂，建议找有经验的货代配合
- 南非要求最严格，部分建材需要当地测试

告诉我您的目标市场，我为您提供详细的合规路线图！`,
    },
  ],
  fallback: "感谢您的提问！合规资质查询涉及较多专业细节，我目前能回答主要非洲国家的认证要求。\n\n如需更精确的合规方案，请通过 WhatsApp 联系我们的合规团队，我们将为您提供一对一的专业指导 💬",
  fallbackL10n: {
    zh: "感谢您的提问！合规资质查询涉及较多专业细节，我目前能回答主要非洲国家的认证要求。\n\n如需更精确的合规方案，请通过 WhatsApp 联系我们的合规团队，我们将为您提供一对一的专业指导 💬",
    en: "Thanks for your question! Compliance queries involve many details — I currently cover major African countries' certification requirements.\n\nFor tailored compliance solutions, contact our team via WhatsApp for one-on-one guidance 💬",
    sw: "Asante kwa swali lako! Maswali ya uzingatiaji yanahusisha maelezo mengi — kwa sasa ninashughulikia mahitaji ya uthibitisho ya nchi kuu za Afrika.\n\nKwa masuluhisho maalum, wasiliana na timu yetu kupitia WhatsApp 💬",
  },
};

// ─── 智能采购助手 ──────────────────────────────────
const procurementAgent: AgentDef = {
  id: "procurement",
  icon: "🔍",
  color: "bg-teal-50",
  accentHex: "#10b981",
  greeting: "你好！我是 Matgo 筑达 智能采购助手 🔍\n\n我可以帮你：\n• 根据项目需求推荐采购方案\n• 规划最优物流路径和运输方式\n• 提供供应商匹配和价格参考\n\n请描述您的采购需求，或点击下方快捷问题。",
  greetingL10n: {
    zh: "你好！我是 Matgo 筑达 智能采购助手 🔍\n\n我可以帮你：\n• 根据项目需求推荐采购方案\n• 规划最优物流路径和运输方式\n• 提供供应商匹配和价格参考\n\n请描述您的采购需求，或点击下方快捷问题。",
    en: "Hello! I'm Matgo Smart Procurement Assistant 🔍\n\nI can help you:\n• Recommend procurement plans based on project needs\n• Plan optimal logistics routes and shipping methods\n• Match suppliers and provide price references\n\nDescribe your needs, or tap a quick question below.",
    sw: "Habari! Mimi ni Msaidizi wa Ununuzi wa Akili wa Matgo 🔍\n\nNinaweza kukusaidia:\n• Kupendekeza mipango ya ununuzi kulingana na mradi\n• Kupanga njia bora za usafirishaji\n• Kulinganisha wasambazaji na bei\n\nEleza mahitaji yako, au bonyeza swali hapo chini.",
  },
  suggestions: ["坦桑尼亚学校项目需要哪些建材？", "宁波到达累斯的物流路线", "建材采购有什么省钱技巧？"],
  suggestionsL10n: {
    zh: ["坦桑尼亚学校项目需要哪些建材？", "宁波到达累斯的物流路线", "建材采购有什么省钱技巧？"],
    en: ["What materials for a school project in Tanzania?", "Shipping route from Ningbo to Dar es Salaam", "Cost-saving tips for building materials"],
    sw: ["Vifaa gani kwa mradi wa shule Tanzania?", "Njia ya usafirishaji kutoka Ningbo hadi Dar es Salaam", "Vidokezo vya kuokoa gharama za vifaa vya ujenzi"],
  },
  qa: [
    {
      keywords: ["学校", "项目", "坦桑尼亚", "建材"],
      answer: `好的，为您规划坦桑尼亚学校项目的建材采购方案：

🏫 **学校项目建材清单（标准 4 教室校舍）**

📦 **主体结构**
| 品类 | 规格 | 参考用量 |
|------|------|---------|
| 螺纹钢 | Ø12/Ø16 | 15-20 吨 |
| 彩钢瓦 | 0.4mm 镀锌 | 800-1200 ㎡ |
| 铝合金窗 | 推拉窗 | 40-60 ㎡ |

🔧 **装饰材料**
| 品类 | 规格 | 参考用量 |
|------|------|---------|
| 瓷砖 | 600×600 | 600-800 ㎡ |
| PVC 管 | DN20-110 | 200-300m |
| 电线 | BV 2.5/4.0 | 2000-3000m |
| 开关插座 | 86 型 | 100-150 个 |

🚢 **物流方案推荐**
| 方案 | 柜型 | 总周期 |
|------|------|--------|
| A. 一次发运 | 2×20GP | 35-45 天 |
| B. 分批发运 | 先钢材后装饰 | 分 2 批 |

💡 **省钱建议**：
1. 钢材和瓷砖可以 **混装同柜**（重量+体积互补）
2. 提前 2 周预订舱位，避开旺季加价

需要我为您生成详细的采购清单吗？`,
    },
    {
      keywords: ["宁波", "达累斯", "物流", "路线", "路径"],
      answer: `好的，为您规划宁波到达累斯萨拉姆的物流路线：

🚢 **海运路线方案对比**

📍 **方案 A：直航（推荐）**
\`\`\`
宁波 → 科伦坡(中转) → 达累斯萨拉姆
\`\`\`
| 项目 | 详情 |
|------|------|
| 船公司 | COSCO / MSC / PIL |
| 船期 | 每周 2-3 班 |
| 航程 | 22-28 天 |
| 20GP 运费 | $1,800-2,200 |
| 40HQ 运费 | $3,000-3,600 |
| 优势 | 班次多，时效稳定 |

📍 **方案 B：经新加坡中转**
\`\`\`
宁波 → 新加坡(中转) → 达累斯萨拉姆
\`\`\`
| 项目 | 详情 |
|------|------|
| 船公司 | Evergreen / ONE / Hapag |
| 航程 | 25-35 天 |
| 20GP 运费 | $1,600-2,000 |
| 优势 | 价格较低 |
| 劣势 | 中转时间不确定 |

📍 **方案 C：经吉达/萨拉拉中转**
\`\`\`
宁波 → 吉达/萨拉拉(中转) → 达累斯萨拉姆
\`\`\`
| 项目 | 详情 |
|------|------|
| 航程 | 28-38 天 |
| 适用 | 淡季低价舱位 |

⏱️ **全程时间线**
| 阶段 | 时间 |
|------|------|
| 工厂备货 | 7-15 天 |
| 内陆运输到港 | 1-2 天 |
| 报关放行 | 1-3 天 |
| 海运 | 22-35 天 |
| 目的港清关 | 5-10 天 |
| 本地配送 | 1-3 天 |
| **总计** | **37-68 天** |

需要我帮您联系货代获取实时报价吗？`,
    },
    {
      keywords: ["省钱", "技巧", "降低", "成本"],
      answer: `好的，分享建材采购的省钱实战技巧：

💰 **Matgo 筑达 采购省钱指南**

🏭 **采购端**
| 策略 | 节省幅度 | 说明 |
|------|---------|------|
| 拼单采购 | 10-20% | 多个项目合并同品类订单，提高议价能力 |
| 避开旺季 | 5-15% | 3-4 月和 9-10 月是中国建材淡季 |
| 工厂直采 | 15-25% | 跳过中间贸易商，Matgo 筑达 直连产地 |
| 替代材料 | 10-30% | 如国产品牌替代进口品牌同等质量 |

🚢 **物流端**
| 策略 | 节省幅度 | 说明 |
|------|---------|------|
| 拼柜共享 | 40-60% | 多订单拼柜，分摊整柜运费 |
| 提前订舱 | 10-20% | 提前 2-3 周订舱锁定低价 |
| 重轻搭配 | 15-25% | 瓷砖(重) + PVC管(轻) 同柜最优 |
| 内陆集货 | 5-10% | 多工厂货物集中到一个港口出运 |

📋 **合规端**
| 策略 | 节省幅度 | 说明 |
|------|---------|------|
| PC 证书复用 | $1,000+/年 | SONCAP PC 一次申请多次使用 |
| 批量验货 | 30-50% | 多品类同批验货，分摊检验费 |
| 指定 HS Code | 5-15% | 精准归类可能适用更低税率 |

想了解某个具体品类的省钱方案吗？提交询价后我们会为您定制最优方案！`,
    },
    {
      keywords: ["供应商", "推荐", "工厂", "选品"],
      answer: `好的，为您介绍 Matgo 筑达 的工厂资源：

🏭 **Matgo 筑达 — 直连中国优质工厂**

我们直接对接中国各品类核心产区的优质工厂，确保产品质量和供应稳定。

📊 **工厂筛选标准**
| 维度 | 评估内容 |
|------|---------|
| 🏭 生产能力 | 产能、设备、工艺水平 |
| ✅ 资质认证 | ISO、CE、目的国认证 |
| 📦 出口经验 | 非洲市场出口记录 |
| ⭐ 履约评分 | 交期准时率、品质合格率 |
| 🛡️ 售后保障 | 质保政策、投诉处理 |

🏗️ **建材品类核心产区**
| 品类 | 核心产区 |
|------|---------|
| 瓷砖 | 佛山/淄博 |
| 钢材 | 唐山/日照 |
| PVC管 | 佛山/台州 |
| 电线电缆 | 宁波/天津 |
| 五金件 | 永康/温州 |

告诉我您需要采购的品类和数量，我们为您匹配最合适的工厂！`,
    },
  ],
  fallback: "感谢您的提问！我目前可以回答建材采购方案、物流路线规划和省钱技巧相关问题。\n\n如需获取报价或了解工厂详情，请通过 WhatsApp 联系我们的采购顾问 💬",
  fallbackL10n: {
    zh: "感谢您的提问！我目前可以回答建材采购方案、物流路线规划和省钱技巧相关问题。\n\n如需获取报价或了解工厂详情，请通过 WhatsApp 联系我们的采购顾问 💬",
    en: "Thanks for your question! I currently cover procurement plans, logistics routing and cost-saving tips.\n\nFor live quotes or supplier connections, contact our procurement team via WhatsApp 💬",
    sw: "Asante kwa swali lako! Kwa sasa ninashughulikia mipango ya ununuzi, njia za usafirishaji na vidokezo vya kuokoa gharama.\n\nKwa bei za moja kwa moja au kuunganishwa na wasambazaji, wasiliana na timu yetu kupitia WhatsApp 💬",
  },
};

// ─── AI 智能找货 ──────────────────────────────────
const finderAgent: AgentDef = {
  id: "finder",
  icon: "🛒",
  color: "bg-[#fdf4dc]",
  accentHex: "#c1850b",
  greeting: "你好！我是 Matgo 筑达 AI 找货助手 🛒\n\n告诉我你想找什么，我帮你一键定位：\n• 直接说品类名称，如「劳保手套」「角磨机」\n• 描述你的场景，如「装修需要的水电材料」\n• 说出项目需求，如「学校建设需要什么」\n\n不用自己翻目录，开口就能找到！",
  greetingL10n: {
    zh: "你好！我是 Matgo 筑达 AI 找货助手 🛒\n\n告诉我你想找什么，我帮你一键定位：\n• 直接说品类名称，如「劳保手套」「角磨机」\n• 描述你的场景，如「装修需要的水电材料」\n• 说出项目需求，如「学校建设需要什么」\n\n不用自己翻目录，开口就能找到！",
    en: "Hello! I'm Matgo AI Product Finder 🛒\n\nTell me what you're looking for:\n• Product name, e.g. \"safety gloves\", \"angle grinder\"\n• Your scenario, e.g. \"electrical materials for renovation\"\n• Project needs, e.g. \"what do I need for a school build\"\n\nNo browsing needed — just ask!",
    sw: "Habari! Mimi ni Mtafutaji wa Bidhaa wa AI wa Matgo 🛒\n\nNiambie unatafuta nini:\n• Jina la bidhaa, mfano \"glavu za usalama\", \"grinder\"\n• Hali yako, mfano \"vifaa vya umeme kwa ukarabati\"\n• Mahitaji ya mradi, mfano \"ninahitaji nini kwa shule\"\n\nHakuna haja ya kutafuta — uliza tu!",
  },
  suggestions: ["我想找劳保安防手套", "有没有电动工具？", "装修要用的瓷砖和涂料"],
  suggestionsL10n: {
    zh: ["我想找劳保安防手套", "有没有电动工具？", "装修要用的瓷砖和涂料"],
    en: ["Looking for safety gloves", "Do you have power tools?", "Tiles and paint for renovation"],
    sw: ["Natafuta glavu za usalama", "Mna zana za umeme?", "Vigae na saruji kwa ukarabati"],
  },
  qa: [
    {
      keywords: ["劳保", "手套", "安防", "防护", "安全帽", "反光", "背心", "眼镜", "口罩", "工作服", "safety", "glove", "helmet"],
      answer: `找到了！为您定位 **劳保安防** 品类：

🧤 **劳保安防产品**
| 产品 | 规格 |
|------|------|
| 丁腈涂胶手套 | 13针涤纶，M/L/XL |
| 乳胶皱纹手套 | 棉纱内衬，防滑 |
| PVC 浸胶手套 | 全涂/半涂，防油 |
| 牛皮焊接手套 | 加长袖口，耐高温 |
| 一次性丁腈手套 | 无粉，蓝色/黑色 |

👉 [浏览劳保商品 →](/mall?cat=01)　|　[浏览安防商品 →](/mall?cat=02)

如需了解价格，请将商品加入询价篮提交询价，我们会尽快为您报价！
还需要其他防护用品吗？安全帽、反光背心、防护眼镜我都能帮你找！`,
    },
    {
      keywords: ["电动工具", "角磨机", "电钻", "切割", "工具", "扳手", "电锤", "磨机", "tool", "grinder", "drill"],
      answer: `找到了！为您定位 **电动工具** 品类：

🔧 **热门电动工具**
| 产品 | 规格 | 品牌参考 |
|------|------|---------|
| 角磨机 | 100mm | 东成/博世 |
| 冲击钻 | 13mm | 东成/牧田 |
| 电锤 | 26mm | 东成/博世 |
| 手持切割机 | 355mm | 东成/DCA |
| 电动扳手 | — | 大艺/南威 |

💡 **采购建议**：
- 东非市场偏好 **东成、大艺** 等性价比品牌
- 电压注意选 **220V/50Hz**（坦桑尼亚/肯尼亚通用）
- 建议搭配 **配件包**（钻头、磨片、碳刷）

👉 [浏览手动工具 →](/mall?cat=04)　|　[浏览磨具磨料 →](/mall?cat=06)

如需了解价格，请将商品加入询价篮提交询价！`,
    },
    {
      keywords: ["瓷砖", "水泥", "装修", "地砖", "墙砖", "涂料", "防水", "tile", "cement", "decoration"],
      answer: `找到了！为您整理 **装修建材** 清单：

🏠 **装修核心建材**

📦 **地面/墙面**
| 产品 | 规格 |
|------|------|
| 抛光砖 | 600×600mm |
| 仿古砖 | 600×600mm |
| 木纹砖 | 200×1000mm |
| 外墙砖 | 60×240mm |

👉 [浏览装饰材料 →](/mall?cat=19)　|　[浏览涂料化工 →](/mall?cat=18)

🔌 **水电材料**
| 产品 | 规格 |
|------|------|
| PVC 线管 | DN16/20/25 |
| BV 电线 | 2.5mm²/4mm² |
| PPR 水管 | DN20/25/32 |
| 开关插座 | 86型 |

👉 [浏览电线电缆 →](/mall?cat=12)　|　[浏览电器 →](/mall?cat=10)

看到感兴趣的商品可以直接加入询价篮，提交后我们会尽快为您报价！`,
    },
    {
      keywords: ["门", "窗", "铝合金", "木门", "五金", "门锁", "合页", "door", "window", "hardware"],
      answer: `找到了！为您定位 **门窗五金** 品类：

🚪 **门窗产品**
| 产品 | 规格 |
|------|------|
| 实木复合门 | 标准门洞 |
| 钢质入户门 | 标准/非标 |
| 铝合金推拉窗 | 定制尺寸 |
| 断桥铝窗 | 定制尺寸 |
| 铝合金百叶窗 | 定制尺寸 |

🔩 **配套五金**：门锁、合页、门吸、闭门器等

👉 [浏览门窗 →](/mall?cat=20)　|　[浏览五金丝网 →](/mall?cat=09)

如需了解价格，请将商品加入询价篮提交询价，我们会尽快为您报价！`,
    },
    {
      keywords: ["螺丝", "螺栓", "紧固件", "膨胀", "密封", "玻璃胶", "发泡", "防水", "screw", "bolt", "fastener", "seal"],
      answer: `找到了！为您定位 **紧固密封** 品类：

🔩 **紧固件产品**
| 产品 | 规格 |
|------|------|
| 外六角螺栓 | M8-M20 |
| 膨胀螺栓 | M8-M16 |
| 自攻螺钉 | 各规格 |
| 钢结构螺栓 | 10.9级/8.8级 |

🔧 **密封材料**：玻璃胶、发泡剂、防水卷材、生料带等

👉 [浏览紧固件 →](/mall?cat=08)

需要哪种规格？告诉我用途我来帮你选型！`,
    },
    {
      keywords: ["学校", "建设", "项目", "工地", "施工", "建筑", "project", "school", "construction"],
      answer: `好的！学校建设涉及多个品类，我帮你一站式定位：

🏫 **学校项目所需建材一览**

| 用途 | 推荐品类 | 浏览商品 |
|------|---------|---------|
| 主体结构 | 螺纹钢、钢管 | [浏览 →](/mall?cat=08) |
| 屋面 | 彩钢瓦、防水卷材 | [浏览 →](/mall?cat=17) |
| 门窗 | 铝合金窗、钢质门 | [浏览 →](/mall?cat=20) |
| 地面 | 瓷砖 600×600 | [浏览 →](/mall?cat=27) |
| 水电 | PVC管、电线、开关 | [浏览 →](/mall?cat=12) |
| 安全 | 安全帽、反光背心 | [浏览 →](/mall?cat=01) |
| 工具 | 角磨机、电锤 | [浏览 →](/mall?cat=04) |

需要我帮你生成采购清单吗？提交询价后我们会尽快报价！`,
    },
  ],
  fallback: "我目前覆盖 30+ 建材品类，你可以试着描述：\n• 品类名称（如「安全帽」「PVC管」）\n• 使用场景（如「道路施工需要什么」）\n\n如果没找到你要的，说明我们正在上新，可以通过 WhatsApp 联系采购顾问 💬",
  fallbackL10n: {
    zh: "我目前覆盖 30+ 建材品类，你可以试着描述：\n• 品类名称（如「安全帽」「PVC管」）\n• 使用场景（如「道路施工需要什么」）\n\n如果没找到你要的，说明我们正在上新，可以通过 WhatsApp 联系采购顾问 💬",
    en: "I currently cover 30+ building material categories. Try describing:\n• Product name (e.g. \"safety helmet\", \"PVC pipe\")\n• Use case (e.g. \"what do I need for road construction\")\n\nCan't find it? Contact our procurement team via WhatsApp 💬",
    sw: "Kwa sasa ninashughulikia aina 30+ za vifaa vya ujenzi. Jaribu kueleza:\n• Jina la bidhaa (mfano \"kofia ya usalama\", \"bomba la PVC\")\n• Matumizi (mfano \"ninahitaji nini kwa ujenzi wa barabara\")\n\nHukupata? Wasiliana na timu yetu kupitia WhatsApp 💬",
  },
};

export const AGENTS: AgentDef[] = [containerAgent, complianceAgent, procurementAgent, finderAgent];

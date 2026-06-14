/**
 * 品牌字符串单一来源(Single Source of Truth)。
 *
 * 所有显示品牌名 / Logo 字 / 平台定位 / SEO 描述 的位置都从这里取,
 * 避免硬编码不同步。
 */
export const BRAND = {
  /** 短品牌名:Logo 旁、Header、登录页 H1、首页 H1 */
  name: "东非建材采购平台",

  /** 英文副标题 */
  nameEn: "East Africa Building Materials Procurement Platform",

  /** 英文短标 */
  nameEnShort: "East Africa Building Materials Procurem...",

  /** Logo 单字:Header / 登录页 / favicon */
  logoChar: "建",

  /** 长定位语:平台属性短句(slogan) */
  tagline: "东非建材采购入口 · Built for East Africa",

  /** 浏览器 tab 完整 title */
  fullTitle: "东非建材采购平台 - East Africa Building Materials Procurement",

  /** SEO description meta + 首页 hero 描述段 */
  description:
    "面向坦桑尼亚本地门店、批发商、承包商和项目客户的 B2B 建材采购平台",

  /** WhatsApp 客服号码(东非) */
  whatsapp: "+255 697 123 456",

  /** 默认交付城市 */
  deliverTo: "Dar es Salaam, TZ",
} as const;

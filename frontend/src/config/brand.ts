/**
 * 品牌字符串单一来源(Single Source of Truth)。
 *
 * 所有显示品牌名 / Logo 字 / 平台定位 / SEO 描述 的位置都从这里取,
 * 避免硬编码不同步。
 */
export const BRAND = {
  /** 短品牌名:Logo 旁、Header、登录页 H1、首页 H1 */
  name: "Matgo",

  /** 中文品牌名 */
  nameZh: "筑达",

  /** 英文副标题 */
  nameEn: "China Building Materials for East Africa",

  /** 中文副标题 */
  nameZhSub: "中国建材直采服务东非市场",

  /** Logo 图片路径(小 mark) */
  logoMark: "/logos/logo-mark.png",

  /** Logo 横版图片路径 */
  logoHorizontal: "/logos/logo-horizontal.png",

  /** Logo icon 路径(favicon / apple-touch-icon) */
  logoIcon: "/logos/matgo-icon.png",

  /** 长定位语:平台属性短句(slogan) */
  tagline:
    "China Building Materials for East Africa · 中国建材直采服务东非市场",

  /** 浏览器 tab 完整 title */
  fullTitle: "Matgo 筑达 - China Building Materials for East Africa",

  /** SEO description meta + 首页 hero 描述段 */
  description:
    "面向坦桑尼亚本地门店、批发商、承包商和项目客户的 B2B 建材采购平台",

  /** 默认交付城市 */
  deliverTo: "Dar es Salaam, TZ",
} as const;

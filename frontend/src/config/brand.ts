/**
 * 品牌字符串单一来源(Single Source of Truth)。
 *
 * 所有显示品牌名 / Logo 字 / 平台定位 / SEO 描述 的位置都从这里取,
 * 避免硬编码不同步。
 *
 * TODO(品牌):当前是占位"基建严选",待团队最终定调后只改本文件即可。
 */
export const BRAND = {
  /** 短品牌名:Logo 旁、Header、登录页 H1、首页 H1 */
  name: "基建严选",

  /** 英文副标题:登录页品牌区 subtitle、视觉强化用 */
  nameEn: "JIJIAN SELECT",

  /** Logo 单字:Header / 登录页 / favicon */
  logoChar: "基",

  /** 长定位语:平台属性短句(slogan) */
  tagline: "央企海外 EPC 供应链平台",

  /** 浏览器 tab 完整 title(短品牌 + 定位语 dash 拼接) */
  fullTitle: "基建严选 - 央企海外EPC供应链平台",

  /** SEO description meta + 首页 hero 描述段 */
  description: "面向中国央企海外 EPC 项目的 B2B 工业品供应链平台",
} as const;

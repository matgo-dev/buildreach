/**
 * 品类楼层 Mock 商品数据 — 当 API 无数据时用于首页展示。
 * TODO: 真实商品数据入库后移除此文件。
 */
import type { ProductPublic } from "@/lib/api/products";

type MockProduct = Pick<ProductPublic, "id" | "spu_code" | "name" | "main_image" | "moq" | "moq_unit" | "unit" | "category_code" | "category_name" | "description" | "origin" | "brand" | "certifications" | "is_featured" | "supply_mode">;

function mp(id: number, name: string, seed: string, moq: number, unit: string, categoryCode: string): MockProduct {
  return {
    id, spu_code: `MOCK-${id}`, name,
    // picsum.photos — 可靠的占位图服务，seed 保证同一商品始终同一张图
    main_image: `https://picsum.photos/seed/${seed}/400/400`,
    moq, moq_unit: unit, unit, category_code: categoryCode,
    category_name: "", description: null, origin: "China",
    brand: null, certifications: null, is_featured: true,
    supply_mode: "SUPPLIER_DIRECT",
  };
}

export const MOCK_FLOOR_PRODUCTS: Record<string, MockProduct[]> = {
  // ── 工具耗材 ──
  "01": [
    mp(901, "博世冲击钻 GSB 550",     "drill",      5, "PCS", "01"),
    mp(902, "角磨机 100mm 850W",      "grinder",    10, "PCS", "01"),
    mp(903, "扳手套装 12件组合",        "wrench",     3, "SET", "01"),
    mp(904, "十字螺丝刀套装",           "screwdriver", 10, "SET", "01"),
    mp(905, "5M 钢卷尺 自锁",          "tapemeasure", 50, "PCS", "01"),
    mp(906, "尖嘴钳 8寸 绝缘柄",       "pliers",     20, "PCS", "01"),
    mp(907, "套筒扳手 46件套",          "socketset",  5, "SET", "01"),
    mp(908, "电工剥线钳 多功能",        "wirecutter", 30, "PCS", "01"),
  ],
  // ── 劳保安防 ──
  "02": [
    mp(911, "ABS 安全帽 V型 透气",     "helmet",     50, "PCS", "02"),
    mp(912, "防冲击护目镜 防雾",        "goggles",    100, "PCS", "02"),
    mp(913, "耐磨防割手套 PU涂层",      "gloves",     200, "PAIR", "02"),
    mp(914, "劳保安全鞋 钢包头",        "safetyboot", 20, "PAIR", "02"),
    mp(915, "KN95 防尘口罩 50只装",     "mask",       10, "BOX", "02"),
    mp(916, "反光安全背心 荧光黄",       "vest",       100, "PCS", "02"),
    mp(917, "隔音耳罩 降噪30dB",        "earmuff",    50, "PCS", "02"),
    mp(918, "全身式安全带 双钩",         "harness",    10, "PCS", "02"),
  ],
  // ── 紧固密封 ──
  "03": [
    mp(921, "六角螺栓 M8×40 镀锌",     "bolt",       500, "PCS", "03"),
    mp(922, "十字自攻螺钉 M4×25",       "screw",      1000, "PCS", "03"),
    mp(923, "平垫圈 M10 不锈钢",        "washer",     2000, "PCS", "03"),
    mp(924, "膨胀锚栓 M10×80",          "anchor",     200, "PCS", "03"),
    mp(925, "尼龙扎带 3.6×200mm",       "cabletie",   100, "BAG", "03"),
    mp(926, "管道卡箍 DN25 不锈钢",      "pipeclamp",  100, "PCS", "03"),
    mp(927, "生料带 PTFE 20M",           "sealtape",   200, "ROLL", "03"),
    mp(928, "橡胶密封垫 DN50",           "gasket",     500, "PCS", "03"),
  ],
  // ── 工控配电 ──
  "04": [
    mp(931, "小型断路器 DZ47 2P 32A",   "breaker",    20, "PCS", "04"),
    mp(932, "BVR 电线 2.5mm² 红 100M",  "cable",      10, "ROLL", "04"),
    mp(933, "86型开关面板 白色",          "switchpanel", 50, "PCS", "04"),
    mp(934, "LED 面板灯 600×600 48W",    "ledpanel",   10, "PCS", "04"),
    mp(935, "接线端子排 TB-1512",         "terminal",   50, "PCS", "04"),
    mp(936, "PVC 电工绝缘胶带",           "etape",      200, "ROLL", "04"),
    mp(937, "线管 PVC 20mm 3M",           "conduit",    100, "PCS", "04"),
    mp(938, "防水接线盒 IP65",             "jbox",       30, "PCS", "04"),
  ],
  // ── 门窗五金 ──
  "05": [
    mp(941, "不锈钢门把手 拉丝",         "doorhandle", 20, "PCS", "05"),
    mp(942, "4寸 不锈钢合页 轴承",       "hinge",      100, "PAIR", "05"),
    mp(943, "窗锁 月牙锁 铝合金",        "windowlock", 100, "PCS", "05"),
    mp(944, "液压闭门器 45-65kg",         "doorcloser", 10, "PCS", "05"),
    mp(945, "柜门拉手 128mm 黑色",        "cabinetpull", 50, "PCS", "05"),
    mp(946, "铜挂锁 40mm 通开",           "padlock",    50, "PCS", "05"),
    mp(947, "推拉门导轨 2M 铝合金",       "slidetrack", 20, "PCS", "05"),
    mp(948, "硅胶门挡 粘贴式",             "doorstop",   200, "PCS", "05"),
  ],
  // ── 装饰建材 ──
  "06": [
    mp(951, "仿古地砖 600×600 防滑",     "tile",       50, "SQM", "06"),
    mp(952, "乳胶漆 内墙 白色 20L",      "paint",      5, "BUCKET", "06"),
    mp(953, "PVC 壁纸 0.53×10M",         "wallpaper",  20, "ROLL", "06"),
    mp(954, "PPR 水管 DN25 4M",           "pvcpipe",    50, "PCS", "06"),
    mp(955, "硅酸盐水泥 42.5 50kg",       "cement",     20, "BAG", "06"),
    mp(956, "SBS 防水卷材 4mm",            "waterproof", 10, "ROLL", "06"),
    mp(957, "耐水腻子粉 20kg",             "putty",      30, "BAG", "06"),
    mp(958, "生态板 E1 18mm",              "mdfboard",   10, "SHEET", "06"),
  ],
};

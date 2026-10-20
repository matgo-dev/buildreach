import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // ── 工作台色板(operator / admin / supplier 继续使用) ──
        brand: {
          DEFAULT: "#003366",
          dark: "#002244",
          mid: "#0F4C81",
          accent: "#FF6B35",
          accentDark: "#e05a25",
          success: "#10B981",
        },

        // ── 买方前台(Mall)主色:炭黑系(中东版 ④ 炭黑 + 明黄,2026-10-19 廖总选定) ──
        // token 名沿用 teal(历史原因,实际是炭黑)。锚点:
        //   700 = 主按钮/顶条/分类栏头 #1F2328;600 = hover;
        //   50/100 = 中性浅灰大面(不带色相,让黄色只出现在操作上)。
        teal: {
          50: "#f1f2f4",
          100: "#eaebed",
          200: "#d2d3d4",
          300: "#a5a7a9",
          400: "#797b7e",
          500: "#4c4f53",
          600: "#35393e",
          700: "#1f2328",
          800: "#1d2025",
          900: "#191b1f",
          950: "#1a1e22",
        },

        // ── 品牌点缀:明黄(操作色:搜索键/立即咨询/客服/选中,必须配炭黑字)、ocean/sea 退为中性灰 ──
        // token 名沿用 lime(历史原因,实际是明黄)。
        lime: {
          DEFAULT: "#ffc20e",
          soft: "#ffd34d",
        },
        ocean: "#848689",
        sea: "#414448",

        // ── 语义色 ──
        navy: "#191b1f",
        ink: "#191b1f",
        "ink-2": "#3a4047",
        muted: "#5f656c",
        line: {
          DEFAULT: "#d9dce0",
          strong: "#bbc1c8",
        },
        // 可输入控件边框:对白底约 3.2:1,满足 WCAG 非文本对比 3:1,又不显得框重
        control: "#797b7e",
        bg: "#f7f8fa",
        whatsapp: "#25d366",
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1rem",
      },
      boxShadow: {
        card: "0 10px 25px -10px rgba(0, 51, 102, 0.25)",
        // 参考 HTML 分层阴影体系
        // 前台阴影:浅、散、近(像物体落在浅色展台上)
        "mall-sm": "0 1px 2px rgba(31,35,40,.04), 0 2px 8px rgba(31,35,40,.04)",
        "mall-md": "0 2px 12px rgba(31,35,40,.05)",
        "mall-lg": "0 6px 20px rgba(31,35,40,.09)",
      },
      maxWidth: {
        mall: "1280px",
      },
    },
  },
  plugins: [],
};

export default config;

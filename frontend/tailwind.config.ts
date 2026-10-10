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

        // ── 买方前台(Mall)主色:与 intro.matgo.ai 统一的深绿系(2026-10-09) ──
        // token 名沿用 teal(历史原因,实际是深绿)。锚点:
        //   700 = 主按钮/顶栏 #103D33;600 = hover #286047;
        //   800/900 = 深色标题与品牌深绿面;50/100 = 浅灰绿/冰青浅底。
        teal: {
          50: "#f2f7f3",
          100: "#e1f3ee",
          200: "#c6dccf",
          300: "#9dbfae",
          400: "#6a9a84",
          500: "#3f7a60",
          600: "#286047",
          700: "#103d33",
          800: "#073e32",
          900: "#123b32",
          950: "#082c24",
        },

        // ── 品牌点缀:柠绿(选中/强调,必须配深绿字)、海洋青(装饰)、深海青(链接/焦点) ──
        lime: {
          DEFAULT: "#b9e46b",
          soft: "#cfed79",
        },
        ocean: "#32bdc9",
        sea: "#127b89",

        // ── 语义色 ──
        navy: "#123b32",
        ink: "#123b32",
        "ink-2": "#3d5751",
        muted: "#5d716c",
        line: {
          DEFAULT: "#d1e3d8",
          strong: "#b5cdbf",
        },
        bg: "#f8faf5",
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
        "mall-sm": "0 1px 2px rgba(18,59,50,.04), 0 2px 8px rgba(18,59,50,.04)",
        "mall-md": "0 2px 12px rgba(18,59,50,.05)",
        "mall-lg": "0 6px 20px rgba(18,59,50,.09)",
      },
      maxWidth: {
        mall: "1280px",
      },
    },
  },
  plugins: [],
};

export default config;

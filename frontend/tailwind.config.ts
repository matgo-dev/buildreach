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

        // ── 买方前台(Mall)主色:深青信任色系 ──
        teal: {
          50: "#f0faf9",
          100: "#e5f4f3",
          700: "#07808b",
          800: "#006773",
          900: "#00505a",
          950: "#003f46",
        },

        // ── 暖金点缀色 ──
        gold: {
          DEFAULT: "#e3a615",
          deep: "#c1850b",
          soft: "#fdf4dc",
        },

        // ── 语义色 ──
        navy: "#102441",
        ink: "#1c314f",
        "ink-2": "#3e5862",
        muted: "#6b7a90",
        line: {
          DEFAULT: "#dbe4ea",
          strong: "#c9d8df",
        },
        bg: "#f4f7f9",
        whatsapp: "#25d366",
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1rem",
      },
      boxShadow: {
        card: "0 10px 25px -10px rgba(0, 51, 102, 0.25)",
        // 参考 HTML 分层阴影体系
        "mall-sm": "0 1px 2px rgba(16,36,65,.05), 0 2px 6px rgba(16,36,65,.04)",
        "mall-md": "0 2px 6px rgba(16,36,65,.05), 0 12px 28px rgba(16,36,65,.07)",
        "mall-lg": "0 8px 20px rgba(16,36,65,.08), 0 28px 60px rgba(16,36,65,.12)",
      },
      maxWidth: {
        mall: "1280px",
      },
    },
  },
  plugins: [],
};

export default config;

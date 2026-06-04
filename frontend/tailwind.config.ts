import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 参考工程色板(以下色值复用自 docs/overseas-supply-platform 参考工程)
        brand: {
          // 主色:深蓝
          DEFAULT: "#003366",
          dark: "#002244",
          mid: "#0F4C81",
          accent: "#FF6B35", // 强调橙
          accentDark: "#e05a25",
          success: "#10B981",
        },
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1rem",
      },
      boxShadow: {
        card: "0 10px 25px -10px rgba(0, 51, 102, 0.25)",
      },
    },
  },
  plugins: [],
};

export default config;

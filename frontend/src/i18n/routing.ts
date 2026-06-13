import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["zh", "en", "sw"],
  defaultLocale: "zh",
  localePrefix: "as-needed",
});

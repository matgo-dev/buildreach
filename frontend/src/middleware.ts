import createMiddleware from "next-intl/middleware";
import { routing } from "@/i18n/routing";

export default createMiddleware(routing);

export const config = {
  matcher: ["/((?!_next|__env\\.js|(?:zh|en|sw)/__env\\.js|favicon.ico|icon.svg|icon.png|api|demos|uploads|images|banners|logos|footer|contact|static).*)"],
};

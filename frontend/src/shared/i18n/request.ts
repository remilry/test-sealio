import { getRequestConfig } from "next-intl/server";
import { defaultLocale, timeZone } from "./config";

/**
 * next-intl's request config (wired in next.config.ts). The locale is fixed: it never reads the
 * request (`requestLocale`), so pages stay static with Cache Components. With several languages,
 * the locale would come from the user's settings here.
 */
export default getRequestConfig(async () => ({
  locale: defaultLocale,
  timeZone,
  messages: (await import(`./messages/${defaultLocale}.json`)).default,
}));

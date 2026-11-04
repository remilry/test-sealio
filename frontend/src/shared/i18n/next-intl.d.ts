import type messages from "./messages/en.json";
import type { Locale } from "./config";

// Type-checks every translation key and its arguments against the English messages.
declare module "next-intl" {
  interface AppConfig {
    Locale: Locale;
    Messages: typeof messages;
  }
}

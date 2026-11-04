/** Languages of the interface. English only for now: a new one is a new messages/<locale>.json. */
export const locales = ["en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "en";
// Swiss tenders: dates and times are shown in Zurich time whatever the server's zone.
export const timeZone = "Europe/Zurich";

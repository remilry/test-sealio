/**
 * The only place in the frontend that manipulates dates (ESLint forbids `Date` and
 * `Intl.DateTimeFormat` elsewhere). Everything goes through these helpers so switching to a
 * date library means changing this file only; `date.test.ts` is the contract to keep.
 */

/** A calendar day as sent by the back: "YYYY-MM-DD". */
export type IsoDate = string;

const MS_PER_DAY = 24 * 60 * 60 * 1000;
const MS_PER_HOUR = 60 * 60 * 1000;

// Swiss format (dd.mm.yyyy); `en-CH` keeps Swiss conventions with the English UI.
const displayFormat = new Intl.DateTimeFormat("en-CH", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

/** "2026-11-19" → that calendar day at local midnight (no UTC shift). */
export function parseIsoDate(isoDate: IsoDate): Date {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day);
}

/** Now. */
export function now(): Date {
  return new Date();
}

/** Today at local midnight. */
export function startOfToday(): Date {
  const current = now();
  return new Date(current.getFullYear(), current.getMonth(), current.getDate());
}

export function addHours(date: Date, hours: number): Date {
  return new Date(date.getTime() + hours * MS_PER_HOUR);
}

/** Calendar days from `from` to `to` (times of day ignored; negative when `to` is earlier). */
export function daysBetween(from: Date, to: Date): number {
  // Compare UTC midnights of both calendar days so daylight saving changes don't skew the count.
  const fromDay = Date.UTC(from.getFullYear(), from.getMonth(), from.getDate());
  const toDay = Date.UTC(to.getFullYear(), to.getMonth(), to.getDate());
  return Math.round((toDay - fromDay) / MS_PER_DAY);
}

/** Calendar days from today to an ISO date: 0 = today, negative = past. */
export function daysUntil(isoDate: IsoDate): number {
  return daysBetween(startOfToday(), parseIsoDate(isoDate));
}

/** "19.11.2026" */
export function formatDate(date: Date | IsoDate): string {
  return displayFormat.format(typeof date === "string" ? parseIsoDate(date) : date);
}

const timeFormat = new Intl.DateTimeFormat("en-CH", { hour: "2-digit", minute: "2-digit" });

/** A timestamp as sent by the back (ISO 8601 with offset) → its local calendar day: "04.11.2026". */
export function formatDay(isoDateTime: string): string {
  return displayFormat.format(new Date(isoDateTime));
}

/** A timestamp as sent by the back (ISO 8601 with offset) → "14:32", in local time. */
export function formatTime(isoDateTime: string): string {
  return timeFormat.format(new Date(isoDateTime));
}

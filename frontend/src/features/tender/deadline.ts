const DAY_MS = 24 * 60 * 60 * 1000;

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

/** "2026-11-19" read as a calendar day in the user's time zone (no UTC shift). */
function calendarDay(isoDate: string): Date {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day);
}

/** Whole days from today to the deadline: 0 = today, negative = past. */
export function daysUntil(isoDate: string, now: Date = new Date()): number {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((calendarDay(isoDate).getTime() - today.getTime()) / DAY_MS);
}

export function formatDaysLeft(days: number): string {
  if (days < 0) return "closed";
  if (days === 0) return "due today";
  return days === 1 ? "1 day" : `${days} days`;
}

/** "19 Nov 2026 · 16 days" */
export function formatDeadline(isoDate: string, now: Date = new Date()): string {
  return `${dateFormat.format(calendarDay(isoDate))} · ${formatDaysLeft(daysUntil(isoDate, now))}`;
}

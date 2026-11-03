import { daysUntil, formatDate, type IsoDate } from "@/shared/utils/date";

/** Wording of the time left before a deadline. */
export function formatDaysLeft(days: number): string {
  if (days < 0) return "closed";
  if (days === 0) return "due today";
  return days === 1 ? "1 day" : `${days} days`;
}

/** "19 Nov 2026 · 16 days" */
export function formatDeadline(deadline: IsoDate): string {
  return `${formatDate(deadline)} · ${formatDaysLeft(daysUntil(deadline))}`;
}

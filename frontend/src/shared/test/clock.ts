import { addHours, parseIsoDate, type IsoDate } from "@/shared/utils/date";

/**
 * Freezes "today" (at 10:00) for the current test. Only `Date` is faked, timers stay real so
 * Testing Library's async queries keep working. Restored after each test by setup.ts.
 */
export function freezeToday(isoDate: IsoDate) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(addHours(parseIsoDate(isoDate), 10));
}

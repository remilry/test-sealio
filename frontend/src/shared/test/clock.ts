/**
 * Freezes "today" for the current test (only `Date` is faked, timers stay real so
 * Testing Library's async queries keep working). Restored after each test by setup.ts.
 */
export function freezeToday(isoDate: string) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(`${isoDate}T10:00:00`));
}

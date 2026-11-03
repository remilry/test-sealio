import { addHours, daysBetween, daysUntil, formatDate, parseIsoDate, startOfToday } from "./date";

// Contract of the date helpers: these tests must keep passing if the implementation
// switches to a date library.
describe("date helpers", () => {
  it("reads an ISO date as that calendar day, at local midnight", () => {
    const date = parseIsoDate("2026-11-19");

    expect(formatDate(date)).toBe("19 Nov 2026");
    expect(daysBetween(date, addHours(date, 23))).toBe(0);
  });

  it("formats a date as day, short month and year", () => {
    expect(formatDate(parseIsoDate("2026-01-05"))).toBe("5 Jan 2026");
  });

  it("counts calendar days, whatever the time of day", () => {
    const morning = addHours(parseIsoDate("2026-11-03"), 1);
    const evening = addHours(parseIsoDate("2026-11-04"), 23);

    expect(daysBetween(morning, evening)).toBe(1);
    expect(daysBetween(evening, morning)).toBe(-1);
  });

  it("counts calendar days across a daylight saving change", () => {
    // Europe switches to winter time on 25 Oct 2026.
    expect(daysBetween(parseIsoDate("2026-10-24"), parseIsoDate("2026-10-26"))).toBe(2);
  });

  it("counts the days from today to a date", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(addHours(parseIsoDate("2026-11-03"), 18));

    expect(daysBetween(startOfToday(), parseIsoDate("2026-11-03"))).toBe(0);
    expect(daysUntil("2026-11-19")).toBe(16);
    expect(daysUntil("2026-11-02")).toBe(-1);
  });
});

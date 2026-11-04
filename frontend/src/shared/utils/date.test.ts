import {
  addHours,
  daysBetween,
  daysUntil,
  formatDate,
  formatDay,
  formatTime,
  isoToMs,
  nowMs,
  parseIsoDate,
  startOfToday,
} from "./date";

// Contract of the date helpers: these tests must keep passing if the implementation
// switches to a date library.
describe("date helpers", () => {
  it("reads an ISO date as that calendar day, at local midnight", () => {
    const date = parseIsoDate("2026-11-19");

    expect(formatDate(date)).toBe("19.11.2026");
    expect(daysBetween(date, addHours(date, 23))).toBe(0);
  });

  it("formats a date the Swiss way: dd.mm.yyyy", () => {
    expect(formatDate(parseIsoDate("2026-01-05"))).toBe("05.01.2026");
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

  it("gives now and a timestamp from the back in milliseconds, to measure durations", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(isoToMs("2026-11-04T10:00:05Z"));

    expect(nowMs() - isoToMs("2026-11-04T10:00:00Z")).toBe(5000);
    expect(isoToMs("2026-11-04T11:00:00+01:00")).toBe(isoToMs("2026-11-04T10:00:00Z"));
  });

  it("formats a timestamp from the back as its local day: dd.mm.yyyy", () => {
    // 23:30 UTC is already the next day in Zurich (UTC+1 in November).
    expect(formatDay("2026-11-03T23:30:00Z")).toBe("04.11.2026");
    expect(formatDay("2026-11-03T09:05:00+01:00")).toBe("03.11.2026");
  });

  it("formats a timestamp from the back as a local time: hh:mm", () => {
    // Zurich is UTC+1 in November.
    expect(formatTime("2026-11-03T13:32:10.123456Z")).toBe("14:32");
    expect(formatTime("2026-11-03T09:05:00+01:00")).toBe("09:05");
  });
});

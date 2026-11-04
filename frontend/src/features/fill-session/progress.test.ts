import { describe, expect, it } from "vitest";
import { initialRun, type FillRun } from "./fill-events";
import { fillProgress } from "./progress";

const SECOND = 1000;
const opts = (now: number) => ({ now, startedAt: 0, estimatedSeconds: 25 });

function searching(k: number, n: number, lastProgressAt: number | null = null): FillRun {
  return {
    ...initialRun,
    phase: "searching",
    toAnswer: n,
    answered: new Set(Array.from({ length: k }, (_, i) => i)),
    lastProgressAt,
  };
}

describe("fillProgress", () => {
  it("stays under 5 % before searching", () => {
    for (const phase of [null, "reading_form", "detecting_fields"] as const) {
      const p = fillProgress({ ...initialRun, phase }, opts(600 * SECOND));
      expect(p).toBeLessThanOrEqual(0.05);
    }
  });

  it("is 1 when done", () => {
    const run: FillRun = {
      ...searching(3, 3),
      outcome: { kind: "done", filled: 3, fillable: 3, seconds: 5 },
    };
    expect(fillProgress(run, opts(SECOND))).toBe(1);
  });

  it("stays between 95 % and 99 % while cross-checking and preparing the review", () => {
    for (const phase of ["cross_checking", "preparing_review"] as const) {
      for (const t of [0, 5, 600]) {
        const p = fillProgress({ ...searching(4, 4, 0), phase }, opts(t * SECOND));
        expect(p).toBeGreaterThanOrEqual(0.95);
        expect(p).toBeLessThan(0.99);
      }
    }
  });

  it("stays within the milestone of k answers out of n", () => {
    for (const t of [0, 3, 30, 600]) {
      const p = fillProgress(searching(2, 5, 0), opts(t * SECOND));
      expect(p).toBeGreaterThanOrEqual(0.05 + (0.9 * 2) / 5);
      expect(p).toBeLessThan(0.05 + (0.9 * 3) / 5);
    }
  });

  it("creeps with time without reaching the next milestone", () => {
    const run = searching(0, 4);
    expect(fillProgress(run, opts(10 * SECOND))).toBeGreaterThan(
      fillProgress(run, opts(2 * SECOND)),
    );
    expect(fillProgress(run, opts(600 * SECOND))).toBeLessThan(0.05 + 0.9 / 4);
  });

  it("creeps from the last answer", () => {
    const run = searching(1, 4, 20 * SECOND);
    expect(fillProgress(run, opts(20 * SECOND))).toBeCloseTo(0.05 + 0.9 / 4);
    expect(fillProgress(run, opts(30 * SECOND))).toBeGreaterThan(0.05 + 0.9 / 4);
  });

  it("creeps below 95 % when the number of fields is unknown", () => {
    for (const toAnswer of [null, 0]) {
      const run: FillRun = { ...initialRun, phase: "searching", toAnswer };
      const a = fillProgress(run, opts(2 * SECOND));
      const b = fillProgress(run, opts(10 * SECOND));
      expect(b).toBeGreaterThan(a);
      expect(fillProgress(run, opts(600 * SECOND))).toBeLessThan(0.95);
    }
  });

  it("never goes back along a run", () => {
    const steps: [FillRun, number][] = [
      [initialRun, 0],
      [{ ...initialRun, phase: "reading_form" }, 1],
      [{ ...initialRun, phase: "detecting_fields", toAnswer: 3 }, 4],
      [searching(0, 3), 6],
      [searching(0, 3), 40],
      [searching(1, 3, 41), 41],
      [searching(1, 3, 41), 100],
      [searching(2, 3, 101), 101],
      [searching(3, 3, 102), 102],
      [{ ...searching(3, 3, 102), phase: "cross_checking" }, 103],
      [{ ...searching(3, 3, 102), phase: "preparing_review" }, 120],
      [
        {
          ...searching(3, 3, 102),
          outcome: { kind: "done", filled: 3, fillable: 3, seconds: 100 },
        },
        121,
      ],
    ];
    let previous = 0;
    for (const [run, t] of steps) {
      const p = fillProgress(run, opts(t * SECOND));
      expect(p).toBeGreaterThanOrEqual(previous);
      previous = p;
    }
  });

  it("does not drop when the last field is answered after a long creep", () => {
    const before = fillProgress(searching(2, 3, 0), opts(600 * SECOND));
    const after = fillProgress(searching(3, 3, 600 * SECOND), opts(600 * SECOND));
    expect(after).toBeGreaterThanOrEqual(before);
    expect(fillProgress(searching(3, 3, 0), opts(6000 * SECOND))).toBeLessThan(0.95);
  });

  it("never drops with an unknown field count while answers arrive", () => {
    let previous = 0;
    for (const [k, t] of [
      [0, 1],
      [0, 10],
      [1, 11],
      [1, 40],
      [2, 41],
      [3, 300],
    ] as const) {
      const run: FillRun = {
        ...initialRun,
        phase: "searching",
        toAnswer: null,
        answered: new Set(Array.from({ length: k }, (_, i) => i)),
        lastProgressAt: k ? t * SECOND : null,
      };
      const p = fillProgress(run, opts(t * SECOND));
      expect(p).toBeGreaterThanOrEqual(previous);
      previous = p;
    }
  });

  it("falls back to 25 s for an invalid estimate", () => {
    const run = searching(0, 3);
    const expected = fillProgress(run, { now: 5 * SECOND, startedAt: 0, estimatedSeconds: 25 });
    for (const estimatedSeconds of [NaN, -3, 0]) {
      expect(fillProgress(run, { now: 5 * SECOND, startedAt: 0, estimatedSeconds })).toBe(expected);
    }
  });
});

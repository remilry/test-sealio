/** Progress of a fill run: always moves, never goes back, reaches 100 % only when done. */
import type { FillRun } from "./fill-events";

const BEFORE_SEARCH_MAX = 0.05;
const SEARCH_END = 0.95;
const REVIEW_END = 0.99;
/** A creep never covers more than this share of the gap to the next milestone. */
const DEFAULT_ESTIMATED_SECONDS = 25;
const CREEP_SHARE = 0.9;

export type ProgressTiming = { now: number; startedAt: number; estimatedSeconds: number };

/** Share of a gap covered after `elapsedMs`, in [0, CREEP_SHARE): 1 - exp(-t / tau), capped. */
function creep(elapsedMs: number, tauSeconds: number): number {
  const t = Math.max(0, elapsedMs) / 1000;
  return CREEP_SHARE * (1 - Math.exp(-t / Math.max(tauSeconds, 0.001)));
}

/**
 * Progress in [0, 1]. Monotonic for the event sequence of a single run; the consumer keeps a
 * high-water mark across stream reconnects (the run is reset and replayed).
 */
export function fillProgress(run: FillRun, timing: ProgressTiming): number {
  if (run.outcome?.kind === "done") return 1;

  const { now, startedAt } = timing;
  const estimatedSeconds =
    Number.isFinite(timing.estimatedSeconds) && timing.estimatedSeconds > 0
      ? timing.estimatedSeconds
      : DEFAULT_ESTIMATED_SECONDS;
  const elapsed = now - (run.lastProgressAt ?? startedAt);
  const total = run.toAnswer ?? 0;
  const tau = estimatedSeconds / (Math.max(total, 1) + 1);

  switch (run.phase) {
    case null:
    case "reading_form":
    case "detecting_fields":
      return BEFORE_SEARCH_MAX * creep(elapsed, estimatedSeconds);
    case "searching": {
      const span = SEARCH_END - BEFORE_SEARCH_MAX;
      // Unknown field count: time only, from the start of the run.
      if (total <= 0) {
        return BEFORE_SEARCH_MAX + span * creep(now - startedAt, estimatedSeconds);
      }
      const gap = span / total;
      const answered = Math.min(run.answered.size, total);
      // Everything answered: creep through the last tenth of the final gap, staying under 95 %.
      if (answered === total) {
        const floor = BEFORE_SEARCH_MAX + gap * (total - 1) + gap * CREEP_SHARE;
        return floor + (SEARCH_END - floor) * creep(elapsed, tau);
      }
      return BEFORE_SEARCH_MAX + gap * answered + gap * creep(elapsed, tau);
    }
    case "cross_checking":
    case "preparing_review":
      return SEARCH_END + (REVIEW_END - SEARCH_END) * creep(elapsed, tau);
  }
}

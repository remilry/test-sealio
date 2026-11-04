/** Progress of a fill run: always moves, never goes back, reaches 100 % only when done. */
import type { FillRun } from "./fill-events";

const BEFORE_SEARCH_MAX = 0.05;
const SEARCH_END = 0.95;
const REVIEW_END = 0.99;
/** A creep never covers more than this share of the gap to the next milestone. */
const CREEP_SHARE = 0.9;

export type ProgressTiming = { now: number; startedAt: number; estimatedSeconds: number };

/** Share of a gap covered after `elapsedMs`, in [0, CREEP_SHARE): 1 - exp(-t / tau), capped. */
function creep(elapsedMs: number, tauSeconds: number): number {
  const t = Math.max(0, elapsedMs) / 1000;
  return CREEP_SHARE * (1 - Math.exp(-t / Math.max(tauSeconds, 0.001)));
}

export function fillProgress(
  run: FillRun,
  { now, startedAt, estimatedSeconds }: ProgressTiming,
): number {
  if (run.outcome?.kind === "done") return 1;

  const elapsed = now - (run.lastProgressAt ?? startedAt);
  const fields = Math.max(run.toAnswer ?? 0, run.answered.size + 1);
  const tau = estimatedSeconds / (fields + 1);

  switch (run.phase) {
    case null:
    case "reading_form":
    case "detecting_fields":
      return BEFORE_SEARCH_MAX * creep(elapsed, estimatedSeconds);
    case "searching": {
      const gap = (SEARCH_END - BEFORE_SEARCH_MAX) / fields;
      return BEFORE_SEARCH_MAX + gap * run.answered.size + gap * creep(elapsed, tau);
    }
    case "cross_checking":
    case "preparing_review":
      return SEARCH_END + (REVIEW_END - SEARCH_END) * creep(elapsed, tau);
  }
}

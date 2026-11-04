"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Progress } from "@/shared/ui/progress";
import { isoToMs, nowMs } from "@/shared/utils/date";
import type { FillRun } from "./fill-events";
import { fillProgress } from "./progress";

const TICK_MS = 250;

/** The current time (ms), refreshed every `intervalMs` so a time-based display keeps moving. */
function useNow(intervalMs: number) {
  const [now, setNow] = useState(nowMs);
  useEffect(() => {
    const timer = setInterval(() => setNow(nowMs()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}

/**
 * The bar of a running fill: always moves (re-rendered every 250 ms), never goes back, even when
 * the stream reconnects and the run is replayed from the start.
 */
export function FillProgress({
  run,
  estimatedSeconds,
  startedAt,
}: {
  run: FillRun;
  /** The back's estimate; unknown (null) falls back to a default duration. */
  estimatedSeconds: number | null;
  /** When the run started (ISO timestamp from the back). */
  startedAt: string;
}) {
  const t = useTranslations("fillProgress");
  const now = useNow(TICK_MS);
  const computed = fillProgress(run, {
    now,
    startedAt: isoToMs(startedAt),
    estimatedSeconds: estimatedSeconds ?? 0,
  });
  // High-water mark: the highest value shown so far (state adjusted during render).
  const [shown, setShown] = useState(computed);
  if (computed > shown) setShown(computed);
  const value = Math.max(shown, computed);

  return <Progress aria-label={t("label")} value={Math.round(value * 1000) / 10} />;
}

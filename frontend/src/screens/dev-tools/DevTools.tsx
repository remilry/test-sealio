"use client";

import { DevResetButton } from "@/features/dev-tools";

/** Helpers shown on every screen in `next dev` only (never in a build, e2e included). */
export function DevTools() {
  if (process.env.NODE_ENV !== "development") return null;
  return <DevResetButton />;
}

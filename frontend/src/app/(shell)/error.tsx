"use client";

import { useEffect } from "react";
import { ErrorPage } from "@/shared/components/ErrorPage";

/** A screen that crashed: the sidebar stays, the screen says so and can be loaded again. */
export default function ScreenError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <ErrorPage onRetry={retry} />
    </div>
  );
}

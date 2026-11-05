"use client";

/* eslint-disable react/jsx-no-literals -- the app itself crashed: this page renders outside its
   providers (no translations), so its few words are written here, in the app's language. */

import { useEffect } from "react";
import "./globals.css";

/** The app shell itself crashed: a page of its own, in plain words, with a way to try again. */
export default function GlobalError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <html lang="en">
      <body className="flex min-h-screen items-center justify-center bg-background p-6 font-sans text-foreground antialiased">
        <title>Formpilot</title>
        <main className="flex max-w-sm flex-col items-center gap-3 text-center">
          <h1 className="text-lg font-semibold">This page couldn&apos;t be shown</h1>
          <p className="text-sm text-muted-foreground">
            Something went wrong on our side. Please try again in a moment.
          </p>
          <button
            type="button"
            className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-muted"
            onClick={() => retry()}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}

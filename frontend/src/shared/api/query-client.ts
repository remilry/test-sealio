import { QueryClient } from "@tanstack/react-query";
import { retryDelay, retryQuery } from "./retry";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      // A read that fails for a passing reason is tried again; "not found" shows at once.
      queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: retryQuery, retryDelay },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

/** One client per server render, one shared client in the browser (Next.js TanStack Query guide). */
export function getQueryClient() {
  if (typeof window === "undefined") return makeQueryClient();
  browserQueryClient ??= makeQueryClient();
  return browserQueryClient;
}

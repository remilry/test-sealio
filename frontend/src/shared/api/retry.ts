import { ApiError } from "./errors";

/** No pause in tests: they would wait for nothing. */
const RETRY_BASE_MS = process.env.NODE_ENV === "test" ? 0 : 500;
const RETRY_MAX_MS = 4000;

/**
 * A failure that may pass: the back unreachable (network) or failing (5xx). A refusal (4xx) or a
 * cancelled request never changes by trying again.
 */
export function isTransient(error: unknown): boolean {
  if (error instanceof ApiError) return error.status >= 500;
  if (error instanceof DOMException && error.name === "AbortError") return false;
  return true;
}

/** TanStack Query `retry` for reads: up to 3 more tries, passing failures only. */
export function retryQuery(failureCount: number, error: unknown): boolean {
  return failureCount < 3 && isTransient(error);
}

/** `retry` for writes that can be made twice safely (saving a field, discarding): up to 2. */
export function retryWrite(failureCount: number, error: unknown): boolean {
  return failureCount < 2 && isTransient(error);
}

/** Pause before a new try: 0.5 s, 1 s, 2 s… up to 4 s. */
export function retryDelay(attempt: number): number {
  return Math.min(RETRY_BASE_MS * 2 ** attempt, RETRY_MAX_MS);
}

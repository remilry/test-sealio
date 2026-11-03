import createClient from "openapi-fetch";
import type { paths } from "./schema.gen";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Typed HTTP client for the FastAPI back; types come from `pnpm gen:api`.
 * `fetch` is looked up at call time (not captured at import) so MSW's interception applies in tests.
 */
export const api = createClient<paths>({
  baseUrl: API_URL,
  fetch: (request) => globalThis.fetch(request),
});

import createClient from "openapi-fetch";
import type { paths } from "./schema.gen";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Typed HTTP client for the FastAPI back; types come from `pnpm gen:api`. */
export const api = createClient<paths>({ baseUrl: API_URL });

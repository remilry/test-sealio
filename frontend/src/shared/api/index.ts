export { api, API_URL } from "./client";
export { ApiError, isNotFound, unwrap } from "./errors";
export type { components, paths } from "./schema.gen";

import type { components } from "./schema.gen";

/** Shorthand for the back's response models: `Schema<"TenderDetail">`. */
export type Schema<Name extends keyof components["schemas"]> = components["schemas"][Name];

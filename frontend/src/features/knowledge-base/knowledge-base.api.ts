/**
 * Company knowledge endpoints: types and HTTP calls only. Components use the hooks of
 * knowledge-base.queries.ts (see the `frontend-data-layer` skill).
 */
import { api, API_URL, unwrap, type Schema } from "@/shared/api";

export type KnowledgeBase = Schema<"KnowledgeBase">;
export type KnowledgeDocument = Schema<"DocumentOut">;

export const knowledgeApi = {
  get: (signal?: AbortSignal) => unwrap(api.GET("/knowledge", { signal })),
};

/** The original company document, as it was added. */
export const documentFileUrl = (documentId: number) =>
  `${API_URL}/knowledge/documents/${documentId}/file`;

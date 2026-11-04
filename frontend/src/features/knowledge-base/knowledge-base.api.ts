/**
 * Company knowledge endpoints: types and HTTP calls only. Components use the hooks of
 * knowledge-base.queries.ts (see the `frontend-data-layer` skill).
 */
import { api, API_URL, unwrap, type Schema } from "@/shared/api";

export type KnowledgeBase = Schema<"KnowledgeBase">;
export type KnowledgeDocument = Schema<"DocumentOut">;

/** File types the back accepts, for the file picker. */
export const ACCEPTED_FILES = ".pdf,.docx";

export const knowledgeApi = {
  get: (signal?: AbortSignal) => unwrap(api.GET("/knowledge", { signal })),
  /** Uploads the files; the back lists them "processing" and indexes them in the background. */
  addDocuments: (files: File[]) =>
    unwrap(
      api.POST("/knowledge/documents", {
        // The generated type describes the multipart field; the body is built as FormData.
        body: { files: [] },
        bodySerializer: () => {
          const form = new FormData();
          for (const file of files) form.append("files", file);
          return form;
        },
      }),
    ),
  remove: (documentId: number) =>
    unwrap(
      api.DELETE("/knowledge/documents/{document_id}", {
        params: { path: { document_id: documentId } },
      }),
    ),
};

/** The original company document, as it was added. */
export const documentFileUrl = (documentId: number) =>
  `${API_URL}/knowledge/documents/${documentId}/file`;

/**
 * Export endpoints: types and HTTP calls only. Components use the hooks of
 * form-export.queries.ts (see the `frontend-data-layer` skill).
 */
import { api, API_URL, unwrap, type Schema } from "@/shared/api";

export type ExportSummary = Schema<"ExportSummary">;

export const exportApi = {
  getSummary: (formId: number, signal?: AbortSignal) =>
    unwrap(api.GET("/forms/{form_id}/export", { params: { path: { form_id: formId } }, signal })),
};

/** The filled file, in the original format (served as an attachment by the back). */
export const exportedFileUrl = (formId: number) => `${API_URL}/forms/${formId}/export/file`;

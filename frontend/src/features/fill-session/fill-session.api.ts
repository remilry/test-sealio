/**
 * Endpoints of a form being filled: types and HTTP calls only. Components use the hooks of
 * fill-session.queries.ts (see the `frontend-data-layer` skill).
 */
import { api, API_URL, unwrap, type Schema } from "@/shared/api";

export type FormDetail = Schema<"FormDetail">;
export type FormField = Schema<"FieldOut">;
export type FillState = Schema<"FillState">;
export type Answer = Schema<"AnswerOut">;

export const fillApi = {
  getForm: (formId: number, signal?: AbortSignal) =>
    unwrap(api.GET("/forms/{form_id}", { params: { path: { form_id: formId } }, signal })),
  getAnswers: (formId: number, signal?: AbortSignal) =>
    unwrap(api.GET("/forms/{form_id}/answers", { params: { path: { form_id: formId } }, signal })),
  saveAnswer: (formId: number, fieldId: number, value: string | null) =>
    unwrap(
      api.PATCH("/forms/{form_id}/fields/{field_id}", {
        params: { path: { form_id: formId, field_id: fieldId } },
        body: { value },
      }),
    ),
};

/** The original file, as the buyer sent it (rendered in the preview). */
export const originalFileUrl = (formId: number) => `${API_URL}/forms/${formId}/file`;

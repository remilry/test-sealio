/**
 * Endpoints of a form being filled: types and HTTP calls only. Components use the hooks of
 * fill-session.queries.ts (see the `frontend-data-layer` skill).
 */
import { createParser } from "eventsource-parser";
import { api, API_URL, ApiError, unwrap, type Schema } from "@/shared/api";
import type { FillEvent } from "./fill-events";

export type FormDetail = Schema<"FormDetail">;
export type FormField = Schema<"FieldOut">;
export type FillState = Schema<"FillState">;
export type Answer = Schema<"AnswerOut">;
export type AiRun = Schema<"AiRun">;

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
  startFill: (formId: number) =>
    unwrap(api.POST("/forms/{form_id}/fill", { params: { path: { form_id: formId } } })),
  discardFill: (formId: number) =>
    unwrap(api.DELETE("/forms/{form_id}/fill", { params: { path: { form_id: formId } } })),
  /**
   * Reads the run's events (`GET /forms/{id}/fill/events`, replayed from the start) and calls
   * `onEvent` for each; resolves when the stream ends. `fetch` + parser: no EventSource in Node.
   */
  streamEvents: async (
    formId: number,
    { signal, onEvent }: { signal?: AbortSignal; onEvent: (event: FillEvent) => void },
  ): Promise<void> => {
    const response = await fetch(`${API_URL}/forms/${formId}/fill/events`, {
      headers: { accept: "text/event-stream" },
      signal,
    });
    if (!response.ok || !response.body) throw new ApiError(response.status, response.statusText);
    const parser = createParser({
      onEvent: (message) => {
        if (!message.event || !message.id) return;
        const data: object = JSON.parse(message.data);
        onEvent({ ...data, id: Number(message.id), type: message.event } as FillEvent);
      },
    });
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) return;
      parser.feed(value);
    }
  },
};

/** The original file, as the buyer sent it (rendered in the preview). */
export const originalFileUrl = (formId: number) => `${API_URL}/forms/${formId}/file`;

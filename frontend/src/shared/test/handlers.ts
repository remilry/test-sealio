import { http, HttpResponse } from "msw";
import { API_URL } from "@/shared/api";
import type {
  ExportSummary,
  FillState,
  FormDetail,
  KnowledgeBase,
  KnowledgeDocument,
  TenderDetail,
  TenderSummary,
} from "./fixtures";

/** An event of the fill stream (the front's `FillEvent` fits; shared code can't import a feature). */
type StreamEvent = { id: number; type: string } & Record<string, unknown>;

const url = (path: string) => `${API_URL}${path}`;

type SaveBody = { value: string | null };

/** MSW handlers for the back's endpoints, built from typed fixtures. */
export const handlers = {
  tenders: (tenders: TenderSummary[]) =>
    http.get(url("/tenders"), () => HttpResponse.json(tenders)),

  tender: (tender: TenderDetail) =>
    http.get(url(`/tenders/${tender.id}`), () => HttpResponse.json(tender)),

  /** `GET /knowledge`; a function is called at each request (the list follows indexing). */
  knowledge: (knowledge: KnowledgeBase | (() => KnowledgeBase)) =>
    http.get(url("/knowledge"), () =>
      HttpResponse.json(typeof knowledge === "function" ? knowledge() : knowledge),
    ),

  /**
   * `POST /knowledge/documents`: records the content type of each request and answers with
   * `respond()` (the documents the back stored, "processing"). The multipart body is not read:
   * under jsdom + Vitest, reading a body built from jsdom Files makes the fetch fail. The files
   * themselves are checked by the back's tests and the e2e scenario.
   */
  addDocuments: (respond: () => KnowledgeDocument[]) => {
    const requests: { contentType: string | null }[] = [];
    const handler = http.post(url("/knowledge/documents"), ({ request }) => {
      requests.push({ contentType: request.headers.get("content-type") });
      return HttpResponse.json(respond(), { status: 202 });
    });
    return { handler, requests };
  },

  form: (form: FormDetail) => http.get(url(`/forms/${form.id}`), () => HttpResponse.json(form)),

  /** `GET /forms/{id}/answers`; a function is called at each request (the state follows a run). */
  answers: (formId: number, state: FillState | (() => FillState)) =>
    http.get(url(`/forms/${formId}/answers`), () =>
      HttpResponse.json(typeof state === "function" ? state() : state),
    ),

  /** `GET /forms/{id}/export`; a function is called at each request (the summary follows saves). */
  exportSummary: (formId: number, summary: ExportSummary | (() => ExportSummary)) =>
    http.get(url(`/forms/${formId}/export`), () =>
      HttpResponse.json(typeof summary === "function" ? summary() : summary),
    ),

  /**
   * `PATCH /forms/{id}/fields/{fieldId}`: records every request and answers with `respond`
   * (the back's new fill state). `saved.requests` lists `{ fieldId, value }` in order.
   */
  saveField: (formId: number, respond: (fieldId: number, body: SaveBody) => FillState) => {
    const requests: { fieldId: number; value: string | null }[] = [];
    const handler = http.patch<{ fieldId: string }, SaveBody>(
      url(`/forms/${formId}/fields/:fieldId`),
      async ({ params, request }) => {
        const body = await request.json();
        requests.push({ fieldId: Number(params.fieldId), value: body.value });
        return HttpResponse.json(respond(Number(params.fieldId), body));
      },
    );
    return { handler, requests };
  },

  /** `POST /forms/{id}/fill`: counts the starts, answers 202 with a running `AiRun`. */
  startFill: (formId: number) => {
    const state = { starts: 0 };
    const handler = http.post(url(`/forms/${formId}/fill`), () => {
      state.starts += 1;
      return HttpResponse.json(
        { status: "running", started_at: "2026-11-04T10:00:00Z", finished_at: null },
        { status: 202 },
      );
    });
    return { handler, state };
  },

  /** `DELETE /forms/{id}/fill`: counts the discards, answers 204. */
  discardFill: (formId: number) => {
    const state = { discards: 0 };
    const handler = http.delete(url(`/forms/${formId}/fill`), () => {
      state.discards += 1;
      return new HttpResponse(null, { status: 204 });
    });
    return { handler, state };
  },

  /** `POST /dev/reset`: counts the resets, answers 204. */
  resetDemo: () => {
    const state = { resets: 0 };
    const handler = http.post(url("/dev/reset"), () => {
      state.resets += 1;
      return new HttpResponse(null, { status: 204 });
    });
    return { handler, state };
  },

  /**
   * `GET /forms/{id}/fill/events`: an SSE stream driven by the test. `send(event)` writes an event;
   * `close()` ends the stream. Every request (a reload) first gets the events already sent, as the
   * back replays them, then the live ones. `connections()` counts the requests.
   */
  fillEvents: (formId: number) => {
    const sent: StreamEvent[] = [];
    let connections = 0;
    const encoder = new TextEncoder();
    const open = new Set<ReadableStreamDefaultController<Uint8Array>>();
    let closed = false;
    const frame = ({ id, type, ...data }: StreamEvent) =>
      encoder.encode(`id: ${id}\nevent: ${type}\ndata: ${JSON.stringify(data)}\n\n`);
    const handler = http.get(url(`/forms/${formId}/fill/events`), () => {
      connections += 1;
      let mine: ReadableStreamDefaultController<Uint8Array>;
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          mine = controller;
          for (const event of sent) controller.enqueue(frame(event));
          if (closed) controller.close();
          else open.add(controller);
        },
        // The reader went away (unmount, abort): stop writing to it.
        cancel() {
          open.delete(mine);
        },
      });
      return new HttpResponse(body, { headers: { "content-type": "text/event-stream" } });
    });
    return {
      handler,
      connections: () => connections,
      send(event: StreamEvent) {
        sent.push(event);
        for (const controller of open) controller.enqueue(frame(event));
      },
      close() {
        closed = true;
        for (const controller of open) controller.close();
        open.clear();
      },
    };
  },

  /** `DELETE /knowledge/documents/{id}`: records the ids deleted, answers 204. */
  deleteDocument: () => {
    const deleted: number[] = [];
    const handler = http.delete<{ documentId: string }>(
      url("/knowledge/documents/:documentId"),
      ({ params }) => {
        deleted.push(Number(params.documentId));
        return new HttpResponse(null, { status: 204 });
      },
    );
    return { handler, deleted };
  },

  /** Any endpoint answering with an HTTP error. */
  error: (
    path: string,
    status: number,
    detail = "Something went wrong",
    method: "get" | "patch" | "post" | "delete" = "get",
  ) => http[method](url(path), () => HttpResponse.json({ detail }, { status })),
};

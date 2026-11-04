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

  answers: (formId: number, state: FillState) =>
    http.get(url(`/forms/${formId}/answers`), () => HttpResponse.json(state)),

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

  /** Any endpoint answering with an HTTP error. */
  error: (
    path: string,
    status: number,
    detail = "Something went wrong",
    method: "get" | "patch" | "post" = "get",
  ) => http[method](url(path), () => HttpResponse.json({ detail }, { status })),
};

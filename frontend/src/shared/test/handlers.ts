import { http, HttpResponse } from "msw";
import { API_URL } from "@/shared/api";
import type {
  ExportSummary,
  FillState,
  FormDetail,
  KnowledgeBase,
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

  knowledge: (knowledge: KnowledgeBase) =>
    http.get(url("/knowledge"), () => HttpResponse.json(knowledge)),

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
    method: "get" | "patch" = "get",
  ) => http[method](url(path), () => HttpResponse.json({ detail }, { status })),
};

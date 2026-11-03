import { http, HttpResponse } from "msw";
import { API_URL } from "@/shared/api";
import type { TenderDetail, TenderSummary } from "./fixtures";

const url = (path: string) => `${API_URL}${path}`;

/** MSW handlers for the back's endpoints, built from typed fixtures. */
export const handlers = {
  tenders: (tenders: TenderSummary[]) =>
    http.get(url("/tenders"), () => HttpResponse.json(tenders)),

  tender: (tender: TenderDetail) =>
    http.get(url(`/tenders/${tender.id}`), () => HttpResponse.json(tender)),

  /** Any endpoint answering with an HTTP error. */
  error: (path: string, status: number, detail = "Something went wrong") =>
    http.get(url(path), () => HttpResponse.json({ detail }, { status })),
};

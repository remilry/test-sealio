/**
 * Tender endpoints: types and HTTP calls only. Components never call this file: they use the
 * hooks of tender.queries.ts (see the `frontend-data-layer` skill).
 */
import { api, unwrap, type Schema } from "@/shared/api";

export type TenderSummary = Schema<"TenderSummary">;
export type TenderDetail = Schema<"TenderDetail">;
export type FormSummary = Schema<"FormSummary">;

export const tenderApi = {
  list: (signal?: AbortSignal) => unwrap(api.GET("/tenders", { signal })),
  get: (tenderId: number, signal?: AbortSignal) =>
    unwrap(api.GET("/tenders/{tender_id}", { params: { path: { tender_id: tenderId } }, signal })),
};

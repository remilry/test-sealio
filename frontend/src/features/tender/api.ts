import { queryOptions } from "@tanstack/react-query";
import { api, unwrap, type Schema } from "@/shared/api";

export type TenderSummary = Schema<"TenderSummary">;
export type TenderDetail = Schema<"TenderDetail">;
export type FormSummary = Schema<"FormSummary">;

/** Query keys and fetchers of the tender domain. */
export const tenderQueries = {
  all: () =>
    queryOptions({
      queryKey: ["tenders"],
      queryFn: ({ signal }) => unwrap(api.GET("/tenders", { signal })),
    }),
  detail: (tenderId: number) =>
    queryOptions({
      queryKey: ["tenders", tenderId],
      queryFn: ({ signal }) =>
        unwrap(
          api.GET("/tenders/{tender_id}", { params: { path: { tender_id: tenderId } }, signal }),
        ),
    }),
};

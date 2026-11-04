/** Tender data for components: query keys and hooks (the only place that calls useQuery). */
import { queryOptions, useQuery } from "@tanstack/react-query";
import { tenderApi } from "./tender.api";

export const tenderKeys = {
  all: ["tenders"] as const,
  detail: (tenderId: number) => [...tenderKeys.all, tenderId] as const,
};

const tenderQueries = {
  list: () =>
    queryOptions({ queryKey: tenderKeys.all, queryFn: ({ signal }) => tenderApi.list(signal) }),
  detail: (tenderId: number) =>
    queryOptions({
      queryKey: tenderKeys.detail(tenderId),
      queryFn: ({ signal }) => tenderApi.get(tenderId, signal),
    }),
};

/** The open tenders, most urgent first. */
export function useTenders() {
  return useQuery(tenderQueries.list());
}

/** A tender with its forms and the current tenant's status on each. */
export function useTender(tenderId: number) {
  return useQuery(tenderQueries.detail(tenderId));
}

/** Company knowledge for components: query keys and hooks (the only useQuery calls). */
import { queryOptions, useQuery } from "@tanstack/react-query";
import { knowledgeApi } from "./knowledge-base.api";

export const knowledgeKeys = {
  all: ["knowledge"] as const,
};

const knowledgeQueries = {
  base: () =>
    queryOptions({
      queryKey: knowledgeKeys.all,
      queryFn: ({ signal }) => knowledgeApi.get(signal),
    }),
};

/** The current tenant's company documents and their indexing status, newest first. */
export function useKnowledgeBase() {
  return useQuery(knowledgeQueries.base());
}

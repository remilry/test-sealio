/** Company knowledge for components: query keys and hooks (the only useQuery calls). */
import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { knowledgeApi, type KnowledgeBase, type KnowledgeDocument } from "./knowledge-base.api";

/** How often the list is refreshed while a document is being indexed. */
export const PROCESSING_POLL_MS = 1000;

export const knowledgeKeys = {
  all: ["knowledge"] as const,
  add: () => [...knowledgeKeys.all, "add"] as const,
};

const knowledgeQueries = {
  base: () =>
    queryOptions({
      queryKey: knowledgeKeys.all,
      queryFn: ({ signal }) => knowledgeApi.get(signal),
      // Follows documents being indexed until each one is indexed or in error.
      refetchInterval: (query) =>
        query.state.data?.documents.some((document) => document.status === "processing")
          ? PROCESSING_POLL_MS
          : false,
    }),
};

/** The current tenant's company documents and their indexing status, newest first. */
export function useKnowledgeBase() {
  return useQuery(knowledgeQueries.base());
}

/**
 * Adds documents. Once the back has them, they show at the top of the list as "processing" (a
 * document of the same name is replaced) and the list refreshes until they are indexed.
 */
export function useAddDocuments() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: knowledgeKeys.add(),
    mutationFn: (files: File[]) => knowledgeApi.addDocuments(files),
    onSuccess: (added) => {
      queryClient.setQueryData(knowledgeKeys.all, (base: KnowledgeBase | undefined) =>
        base ? withDocuments(base, added) : base,
      );
      void queryClient.invalidateQueries({ queryKey: knowledgeKeys.all });
    },
  });
}

function withDocuments(base: KnowledgeBase, added: KnowledgeDocument[]): KnowledgeBase {
  const ids = new Set(added.map((document) => document.id));
  return {
    ...base,
    documents: [...added, ...base.documents.filter((document) => !ids.has(document.id))],
  };
}

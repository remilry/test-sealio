/** Company knowledge for components: query keys and hooks (the only useQuery calls). */
import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { knowledgeApi, type KnowledgeBase, type KnowledgeDocument } from "./knowledge-base.api";

/** How often the list is refreshed while a document is being indexed. */
export const PROCESSING_POLL_MS = 1000;

export const knowledgeKeys = {
  all: ["knowledge"] as const,
  add: () => [...knowledgeKeys.all, "add"] as const,
  remove: () => [...knowledgeKeys.all, "remove"] as const,
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

/**
 * Deletes a document. Optimistic: it leaves the list at once and comes back if the back fails
 * (the error is then on the mutation, for the screen to explain).
 */
export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: knowledgeKeys.remove(),
    mutationFn: (document: KnowledgeDocument) => knowledgeApi.remove(document.id),
    onMutate: async (document) => {
      await queryClient.cancelQueries({ queryKey: knowledgeKeys.all });
      const previous = queryClient.getQueryData<KnowledgeBase>(knowledgeKeys.all);
      queryClient.setQueryData(knowledgeKeys.all, (base: KnowledgeBase | undefined) =>
        base ? { ...base, documents: base.documents.filter(({ id }) => id !== document.id) } : base,
      );
      return { previous };
    },
    onError: (_error, _document, context) => {
      if (context?.previous) queryClient.setQueryData(knowledgeKeys.all, context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: knowledgeKeys.all }),
  });
}

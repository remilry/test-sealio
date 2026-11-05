import { queryOptions, useQuery } from "@tanstack/react-query";
import { documentPreviewApi } from "./document-preview.api";

export const documentPreviewKeys = {
  all: ["document-files"] as const,
  file: (fileUrl: string) => [...documentPreviewKeys.all, fileUrl] as const,
};

const documentPreviewQueries = {
  file: (fileUrl: string) =>
    queryOptions({
      queryKey: documentPreviewKeys.file(fileUrl),
      queryFn: ({ signal }) => documentPreviewApi.file(fileUrl, signal),
      // An original file never changes: read once.
      staleTime: Infinity,
      retry: false,
    }),
};

/** The bytes of an original file, to render it in the page. */
export function useDocumentFile(fileUrl: string) {
  return useQuery(documentPreviewQueries.file(fileUrl));
}

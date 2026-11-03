import { queryOptions } from "@tanstack/react-query";
import { api, API_URL, unwrap, type Schema } from "@/shared/api";

export type ExportSummary = Schema<"ExportSummary">;

export const exportQueries = {
  summary: (formId: number) =>
    queryOptions({
      queryKey: ["forms", formId, "export"],
      queryFn: ({ signal }) =>
        unwrap(
          api.GET("/forms/{form_id}/export", { params: { path: { form_id: formId } }, signal }),
        ),
      // Always reflect the latest answers.
      staleTime: 0,
    }),
};

/** The filled file, in the original format (served as an attachment by the back). */
export const exportedFileUrl = (formId: number) => `${API_URL}/forms/${formId}/export/file`;

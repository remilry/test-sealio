/** Export data for components: query keys and hooks (the only place that calls useQuery). */
import { useQuery } from "@tanstack/react-query";
import { exportApi } from "./form-export.api";

export const exportKeys = {
  summary: (formId: number) => ["forms", formId, "export"] as const,
};

/**
 * What the export will contain. Waits while `enabled` is false (a value is being saved), and is
 * always refetched: it must reflect the latest answers.
 */
export function useExportSummary(formId: number, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: exportKeys.summary(formId),
    queryFn: ({ signal }) => exportApi.getSummary(formId, signal),
    staleTime: 0,
    enabled,
  });
}

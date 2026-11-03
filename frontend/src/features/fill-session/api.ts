import { queryOptions, useMutation, useMutationState, useQueryClient } from "@tanstack/react-query";
import { api, API_URL, unwrap, type Schema } from "@/shared/api";
import { now } from "@/shared/utils/date";

export type FormDetail = Schema<"FormDetail">;
export type FormField = Schema<"FieldOut">;
export type FillState = Schema<"FillState">;
export type Answer = Schema<"AnswerOut">;

/** Query keys and fetchers of a form being filled. */
export const fillQueries = {
  form: (formId: number) =>
    queryOptions({
      queryKey: ["forms", formId],
      queryFn: ({ signal }) =>
        unwrap(api.GET("/forms/{form_id}", { params: { path: { form_id: formId } }, signal })),
    }),
  answers: (formId: number) =>
    queryOptions({
      queryKey: ["forms", formId, "answers"],
      queryFn: ({ signal }) =>
        unwrap(
          api.GET("/forms/{form_id}/answers", { params: { path: { form_id: formId } }, signal }),
        ),
    }),
};

/** The original file, as the buyer sent it (rendered in the preview). */
export const originalFileUrl = (formId: number) => `${API_URL}/forms/${formId}/file`;

const saveKey = (formId: number) => ["forms", formId, "save"];

type SaveVariables = { fieldId: number; value: string | null };

/**
 * Saves a value typed by the user. Optimistic: the answer shows at once; the back's fill state
 * (counts included) replaces it when it answers, and an error rolls it back.
 */
export function useSaveAnswer(formId: number) {
  const queryClient = useQueryClient();
  const answersKey = fillQueries.answers(formId).queryKey;
  return useMutation({
    mutationKey: saveKey(formId),
    mutationFn: ({ fieldId, value }: SaveVariables) =>
      unwrap(
        api.PATCH("/forms/{form_id}/fields/{field_id}", {
          params: { path: { form_id: formId, field_id: fieldId } },
          body: { value },
        }),
      ),
    onMutate: async ({ fieldId, value }) => {
      await queryClient.cancelQueries({ queryKey: answersKey });
      const previous = queryClient.getQueryData(answersKey);
      queryClient.setQueryData(answersKey, (state) =>
        state ? withAnswer(state, fieldId, value) : state,
      );
      return { previous };
    },
    onSuccess: (state) => queryClient.setQueryData(answersKey, state),
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(answersKey, context.previous);
    },
  });
}

function withAnswer(state: FillState, fieldId: number, value: string | null): FillState {
  const answer: Answer = {
    field_id: fieldId,
    value: value?.trim() || null,
    resolved_by: "user",
    resolved_at: now().toISOString(),
  };
  const exists = state.answers.some((a) => a.field_id === fieldId);
  return {
    ...state,
    answers: exists
      ? state.answers.map((a) => (a.field_id === fieldId ? answer : a))
      : [...state.answers, answer],
  };
}

export type SaveStatus = "idle" | "saving" | "saved" | "failed";

/** Whether the latest edit of the form is saved (for the "✓ Saved" indicator). */
export function useSaveStatus(formId: number): SaveStatus {
  const statuses = useMutationState({
    filters: { mutationKey: saveKey(formId) },
    select: (mutation) => mutation.state.status,
  });
  const latest = statuses.at(-1);
  if (latest === undefined || latest === "idle") return "idle";
  if (latest === "pending") return "saving";
  return latest === "success" ? "saved" : "failed";
}

/** Data of a form being filled, for components: query keys and hooks (the only useQuery calls). */
import { useEffect, useState } from "react";
import {
  queryOptions,
  useMutation,
  useMutationState,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { now } from "@/shared/utils/date";
import { initialRun, reduceRun, type FillEvent, type FillRun } from "./fill-events";
import { fillApi, type Answer, type FillState } from "./fill-session.api";

// The tender's key prefix (tender.queries.ts): features can't import each other.
const TENDERS_KEY = ["tenders"] as const;
const RECONNECT_MS = 300;
const RECONNECT_MAX_MS = 5000;

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      resolve();
    });
  });

export const fillKeys = {
  form: (formId: number) => ["forms", formId] as const,
  answers: (formId: number) => [...fillKeys.form(formId), "answers"] as const,
  save: (formId: number) => [...fillKeys.form(formId), "save"] as const,
};

const fillQueries = {
  form: (formId: number) =>
    queryOptions({
      queryKey: fillKeys.form(formId),
      queryFn: ({ signal }) => fillApi.getForm(formId, signal),
    }),
  answers: (formId: number) =>
    queryOptions({
      queryKey: fillKeys.answers(formId),
      queryFn: ({ signal }) => fillApi.getAnswers(formId, signal),
    }),
};

/** The form with its detected fields, in reading order. */
export function useFormDetail(formId: number) {
  return useQuery(fillQueries.form(formId));
}

/** The current tenant's answers to the form, with the counts. */
export function useFillState(formId: number) {
  return useQuery(fillQueries.answers(formId));
}

type SaveVariables = { fieldId: number; value: string | null };

/**
 * Saves a value typed by the user. Optimistic: the answer shows at once; the back's fill state
 * (counts included) replaces it when it answers, and an error rolls it back, then calls
 * `onFailed` so the screen can keep what was typed.
 */
export function useSaveAnswer(
  formId: number,
  { onFailed }: { onFailed?: (variables: SaveVariables) => void } = {},
) {
  const queryClient = useQueryClient();
  const answersKey = fillQueries.answers(formId).queryKey;
  return useMutation({
    mutationKey: fillKeys.save(formId),
    mutationFn: ({ fieldId, value }: SaveVariables) => fillApi.saveAnswer(formId, fieldId, value),
    onMutate: async ({ fieldId, value }) => {
      await queryClient.cancelQueries({ queryKey: answersKey });
      const previous = queryClient
        .getQueryData(answersKey)
        ?.answers.find((a) => a.field_id === fieldId);
      queryClient.setQueryData(answersKey, (state) =>
        state ? withAnswer(state, fieldId, value) : state,
      );
      return { previous };
    },
    // Only the edited field (and the counts) come from the back: answers streamed in meanwhile stay.
    onSuccess: (saved, { fieldId }) =>
      queryClient.setQueryData(answersKey, (state) =>
        state
          ? {
              ...replaceEntry(
                state,
                fieldId,
                saved.answers.find((a) => a.field_id === fieldId),
              ),
              counts: saved.counts,
            }
          : saved,
      ),
    onError: (_error, variables, context) => {
      queryClient.setQueryData(answersKey, (state) =>
        state ? replaceEntry(state, variables.fieldId, context?.previous) : state,
      );
      onFailed?.(variables);
    },
  });
}

/** Sets (or, when `entry` is undefined, removes) the answer of one field, leaving the others. */
function replaceEntry(state: FillState, fieldId: number, entry: Answer | undefined): FillState {
  const others = state.answers.filter((a) => a.field_id !== fieldId);
  if (!entry) return { ...state, answers: others };
  const exists = others.length !== state.answers.length;
  return {
    ...state,
    answers: exists
      ? state.answers.map((a) => (a.field_id === fieldId ? entry : a))
      : [...state.answers, entry],
  };
}

function withAnswer(state: FillState, fieldId: number, value: string | null): FillState {
  const existing = state.answers.find((a) => a.field_id === fieldId);
  // The user's value replaces the AI's, whose evidence (type, candidates) stays shown.
  const answer: Answer = {
    type: null,
    proposed_value: null,
    candidates: [],
    user_only_reason: null,
    ...existing,
    field_id: fieldId,
    value: value?.trim() || null,
    resolved_by: "user",
    resolved_at: now().toISOString(),
    needs_review: false,
  };
  return {
    ...state,
    answers: existing
      ? state.answers.map((a) => (a.field_id === fieldId ? answer : a))
      : [...state.answers, answer],
  };
}

export type SaveStatus = "idle" | "saving" | "saved" | "failed";

/** Whether the latest edit of the form is saved (for the "✓ Saved" indicator). */
export function useSaveStatus(formId: number): SaveStatus {
  const statuses = useMutationState({
    filters: { mutationKey: fillKeys.save(formId) },
    select: (mutation) => mutation.state.status,
  });
  const latest = statuses.at(-1);
  if (latest === undefined || latest === "idle") return "idle";
  if (latest === "pending") return "saving";
  return latest === "success" ? "saved" : "failed";
}

/** Starts the automatic fill; the tender (status) and the answers are then stale. */
export function useStartFill(formId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => fillApi.startFill(formId),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: TENDERS_KEY }),
        queryClient.invalidateQueries({ queryKey: fillKeys.answers(formId) }),
      ]),
  });
}

/** Discards the form's fill (all answers, the user's too): its cached data goes, the tender refreshes. */
export function useDiscardFill(formId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => fillApi.discardFill(formId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: fillKeys.form(formId) });
      return queryClient.invalidateQueries({ queryKey: TENDERS_KEY });
    },
  });
}

/**
 * Follows the form's fill run while `follow`: reads the event stream (replayed from the start, so a
 * reload resumes), folds it into a `FillRun`, and writes each answer into the cache as it arrives
 * (an answer the user typed is kept). At the end, the answers and the tender are refetched.
 */
export function useFillRun(formId: number, { follow }: { follow: boolean }): FillRun {
  const queryClient = useQueryClient();
  const [run, setRun] = useState<FillRun>(initialRun);

  useEffect(() => {
    if (!follow) return;
    const controller = new AbortController();
    const { signal } = controller;
    const answersKey = fillQueries.answers(formId).queryKey;

    const apply = (event: FillEvent) => {
      setRun((current) => reduceRun(current, event, now().getTime()));
      if (event.type === "field" && event.state === "answered") {
        const { answer, counts } = event;
        queryClient.setQueryData(answersKey, (state) =>
          state ? withAiAnswer(state, answer, counts) : state,
        );
      }
      if (event.type === "done" || event.type === "error") refresh();
    };
    const refresh = () => {
      void queryClient.invalidateQueries({ queryKey: answersKey });
      void queryClient.invalidateQueries({ queryKey: TENDERS_KEY });
    };

    // The stream is replayed from the start at each connection, so reconnecting is idempotent.
    // It ends without `done`/`error` when the connection drops, the back errors, or the fill is
    // discarded elsewhere: refetch (the screen stops following if the run is over), then retry.
    const follow_ = async () => {
      for (let attempt = 0; !signal.aborted; attempt++) {
        let ended = false;
        setRun(initialRun);
        try {
          await fillApi.streamEvents(formId, {
            signal,
            onEvent: (event) => {
              if (event.type === "done" || event.type === "error") ended = true;
              apply(event);
            },
          });
        } catch {
          // Handled below like a stream that stopped early.
        }
        if (signal.aborted || ended) return;
        refresh();
        await sleep(Math.min(RECONNECT_MS * 2 ** attempt, RECONNECT_MAX_MS), signal);
      }
    };
    void follow_();
    return () => controller.abort();
  }, [formId, follow, queryClient]);

  return run;
}

function withAiAnswer(state: FillState, answer: Answer, counts: FillState["counts"]): FillState {
  const existing = state.answers.find((a) => a.field_id === answer.field_id);
  if (existing?.resolved_by === "user") return state;
  return {
    ...state,
    counts,
    answers: existing
      ? state.answers.map((a) => (a.field_id === answer.field_id ? answer : a))
      : [...state.answers, answer],
  };
}

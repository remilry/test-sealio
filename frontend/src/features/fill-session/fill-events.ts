/** Events of a fill run (SSE stream of the back) and the pure reducer that folds them into a run. */
import type { Answer, FillState } from "./fill-session.api";

export type FillPhase =
  "reading_form" | "detecting_fields" | "searching" | "cross_checking" | "preparing_review";

export type FillEvent = { id: number } & (
  | {
      type: "phase";
      phase: FillPhase;
      /** `detecting_fields`: how many fields the run will answer. */
      to_answer?: number;
      fields?: number;
      yes_no?: number;
      signatures?: number;
      documents?: number;
      pages?: number;
      sections?: number;
      file_format?: string;
    }
  | { type: "field"; field_id: number; state: "searching" }
  /** The value the model is writing for a field: not verified yet, replaced by its answer. */
  | { type: "field"; field_id: number; state: "writing"; text: string }
  | {
      type: "field";
      field_id: number;
      state: "answered";
      answer: Answer;
      counts: FillState["counts"];
    }
  | { type: "done"; filled: number; fillable: number; doubts: number; seconds: number }
  | { type: "error"; message: string }
);

export type FillRun = {
  phase: FillPhase | null;
  toAnswer: number | null;
  searching: ReadonlySet<number>;
  answered: ReadonlySet<number>;
  /** The value being written for each field not answered yet (unverified). */
  writing: ReadonlyMap<number, string>;
  /** When the last answer arrived (ms), to estimate the remaining time. */
  lastProgressAt: number | null;
  outcome:
    | null
    | { kind: "done"; filled: number; fillable: number; seconds: number }
    | { kind: "error"; message: string };
};

export const initialRun: FillRun = {
  phase: null,
  toAnswer: null,
  searching: new Set(),
  answered: new Set(),
  writing: new Map(),
  lastProgressAt: null,
  outcome: null,
};

/** Folds one event into the run; `at` is the arrival time (ms). Replaying events gives the same run. */
export function reduceRun(run: FillRun, event: FillEvent, at: number): FillRun {
  switch (event.type) {
    case "phase":
      return {
        ...run,
        phase: event.phase,
        toAnswer: event.to_answer ?? run.toAnswer,
      };
    case "field": {
      if (event.state === "searching") {
        if (run.answered.has(event.field_id)) return run;
        return { ...run, searching: new Set(run.searching).add(event.field_id) };
      }
      if (event.state === "writing") {
        if (run.answered.has(event.field_id)) return run;
        return { ...run, writing: new Map(run.writing).set(event.field_id, event.text) };
      }
      const searching = new Set(run.searching);
      searching.delete(event.field_id);
      const writing = new Map(run.writing);
      writing.delete(event.field_id);
      return {
        ...run,
        searching,
        writing,
        answered: new Set(run.answered).add(event.field_id),
        lastProgressAt: at,
      };
    }
    // At the end, no field is being searched any more (an error can stop a section midway).
    case "done":
      return {
        ...run,
        searching: new Set(),
        writing: new Map(),
        outcome: {
          kind: "done",
          filled: event.filled,
          fillable: event.fillable,
          seconds: event.seconds,
        },
      };
    case "error":
      return {
        ...run,
        searching: new Set(),
        writing: new Map(),
        outcome: { kind: "error", message: event.message },
      };
  }
}

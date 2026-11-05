import type { Schema } from "@/shared/api";

export type FormDetail = Schema<"FormDetail">;
export type FormField = Schema<"FieldOut">;
export type FillState = Schema<"FillState">;
export type Answer = Schema<"AnswerOut">;
export type AiRun = Schema<"AiRun">;
export type ExportSummary = Schema<"ExportSummary">;
export type FieldKind = Schema<"FieldKind">;
type Box = Schema<"Box">;

/** Annex 7 as parsed by the back (positions in points, from the real file). */
const FIELDS: [number, string, string, FieldKind, Box, number, Box[]][] = [
  [
    1,
    "project_number_project_title_project_name",
    "Project number/project title/project name",
    "text",
    { x0: 270.2, y0: 208.6, x1: 535.1, y1: 218.6 },
    216.4,
    [{ x0: 270.2, y0: 208.6, x1: 395.7, y1: 218.6 }],
  ],
  [
    2,
    "name_of_the_contracting_authority",
    "Name of the contracting authority",
    "text",
    { x0: 237.9, y0: 231.9, x1: 535.1, y1: 241.9 },
    239.6,
    [{ x0: 237.9, y0: 231.9, x1: 360.7, y1: 241.9 }],
  ],
  [
    3,
    "name_and_legal_form",
    "Name and legal form",
    "text",
    { x0: 189.5, y0: 293.0, x1: 533.2, y1: 303.0 },
    300.7,
    [],
  ],
  [
    4,
    "business_address",
    "Business address",
    "text",
    { x0: 175.6, y0: 317.7, x1: 533.2, y1: 327.7 },
    325.4,
    [],
  ],
  [
    5,
    "contact_person",
    "Contact person",
    "text",
    { x0: 164.5, y0: 342.4, x1: 533.2, y1: 352.4 },
    350.2,
    [],
  ],
  [6, "telephone", "Telephone", "text", { x0: 143.9, y0: 367.1, x1: 307.7, y1: 377.1 }, 374.9, []],
  [7, "e_mail", "E-mail", "text", { x0: 350.4, y0: 367.1, x1: 533.2, y1: 377.1 }, 374.9, []],
  [
    8,
    "place_and_date",
    "Place and date",
    "text",
    { x0: 337.1, y0: 650.2, x1: 535.1, y1: 660.2 },
    658.0,
    [{ x0: 337.1, y0: 650.2, x1: 527.1, y1: 660.2 }],
  ],
  [
    9,
    "first_name_s_and_surname_s",
    "First name(s) and surname(s)",
    "text",
    { x0: 337.0, y0: 673.5, x1: 535.1, y1: 683.5 },
    681.2,
    [{ x0: 337.0, y0: 673.5, x1: 528.2, y1: 683.5 }],
  ],
  [
    10,
    "signature_s",
    "Signature(s)",
    "signature",
    { x0: 337.1, y0: 696.8, x1: 535.1, y1: 706.8 },
    704.5,
    [{ x0: 337.1, y0: 696.8, x1: 528.2, y1: 706.8 }],
  ],
];

export const annex7Fields: FormField[] = FIELDS.map(
  ([id, key, label, kind, box, baseline, erase]) => ({
    id,
    key,
    section: "Page 1",
    label,
    kind,
    locator: { format: "pdf", page: 0, box, baseline, font_size: 10, erase },
  }),
);

/** The Annex 7 form, as returned by `GET /forms/{id}`. */
export function annex7(overrides: Partial<FormDetail> = {}): FormDetail {
  return {
    id: 2,
    tender_id: 1,
    title: "Annex 7 — Sanctions self-declaration (Art. 29c)",
    file_name: "Annex_7_Self-Declaration_Art29c_Ukraine_Ordinance.pdf",
    file_format: "pdf",
    field_counts: { fields: 10, yes_no: 0, signatures: 1 },
    estimated_fill_seconds: 25,
    pages: [{ width: 595.3, height: 841.9 }],
    fields: annex7Fields,
    ...overrides,
  };
}

/** A value the user entered for a field. */
export function answer(fieldId: number, value: string | null, at = "2026-11-03T13:32:00Z"): Answer {
  return {
    field_id: fieldId,
    value,
    proposed_value: null,
    resolved_by: "user",
    resolved_at: at,
    type: null,
    candidates: [],
    user_only_reason: null,
    needs_review: false,
  };
}

/** A value found automatically for a field (`type` says how sure it is). */
export function aiAnswer(
  fieldId: number,
  value: string | null,
  type: NonNullable<Answer["type"]> = "auto",
  at = "2026-11-04T10:00:10Z",
  extra: Partial<Answer> = {},
): Answer {
  return {
    ...answer(fieldId, value, at),
    resolved_by: "ai",
    proposed_value: value,
    type,
    ...extra,
  };
}

type Citation = Schema<"Citation">;
type Candidate = Schema<"Candidate">;

/** A verified quote from a company document (page 1 unless told otherwise). */
export function citation(overrides: Partial<Citation> = {}): Citation {
  return {
    quote: "Alpenlogic AG, Zurich",
    document_name: "Commercial register extract",
    document_id: 1,
    chunk_id: 11,
    page: 0,
    ...overrides,
  };
}

/** A value the search found, with the quotes that support it. */
export function candidate(
  value: string,
  citations: Citation[] = [citation()],
  extra = {},
): Candidate {
  return { value, citations, source_date: null, valid_until: null, ...extra };
}

/** An automatic fill run in progress (or over), as `FillState.ai_run`. */
export function aiRun(status: AiRun["status"] = "running"): AiRun {
  return {
    status,
    started_at: "2026-11-04T10:00:00Z",
    finished_at: status === "running" ? null : "2026-11-04T10:00:23Z",
  };
}

/** `GET /forms/{id}/answers`: counts are the back's, derived here the same way for consistency. */
export function fillState(
  answers: Answer[] = [],
  fields: FormField[] = annex7Fields,
  ai_run: AiRun | null = null,
): FillState {
  const fillable = fields.filter((field) => field.kind !== "signature");
  const filled = fillable.filter((field) =>
    answers.some((a) => a.field_id === field.id && a.value),
  ).length;
  // Not settled by the user, and empty or with a value to check.
  const open = fillable.filter((field) => {
    const answer = answers.find((a) => a.field_id === field.id);
    if (answer?.resolved_by === "user") return false;
    return !answer?.value || answer.needs_review;
  }).length;
  return {
    counts: {
      fillable: fillable.length,
      filled,
      empty: fillable.length - filled,
      doubts: 0,
      open,
    },
    answers,
    ai_run,
  };
}

/** `GET /forms/{id}/export` for Annex 7 with the given fields filled. */
export function exportSummary(filledIds: number[] = [], overrides: Partial<ExportSummary> = {}) {
  const fillable = annex7Fields.filter((field) => field.kind !== "signature");
  const summary: ExportSummary = {
    file_format: "pdf",
    fillable: fillable.length,
    filled: fillable.filter((field) => filledIds.includes(field.id)).length,
    empty_fields: fillable
      .filter((field) => !filledIds.includes(field.id))
      .map(({ id, label }) => ({ id, label })),
    sign_by_hand: [{ id: 10, label: "Signature(s)" }],
  };
  return { ...summary, ...overrides };
}

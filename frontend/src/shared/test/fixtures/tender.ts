import type { Schema } from "@/shared/api";

export type TenderDetail = Schema<"TenderDetail">;
export type TenderSummary = Schema<"TenderSummary">;
export type FormSummary = Schema<"FormSummary">;

export function form(overrides: Partial<FormSummary> = {}): FormSummary {
  return {
    id: 1,
    title: "Annex 4 — Conditions of participation and self-declaration",
    file_name: "Annex_4_Conditions of Participation and Company Self-Declaration.docx",
    file_format: "docx",
    status: "not_started",
    // Word forms are not parsed yet.
    field_counts: null,
    estimated_fill_seconds: null,
    filling: false,
    ...overrides,
  };
}

/** The seeded tender, as returned by `GET /tenders/{id}`. */
export function tender(overrides: Partial<TenderDetail> = {}): TenderDetail {
  return {
    id: 1,
    reference: "ZH-2026-0412",
    title: "Cloud Platform Services – Canton of Zurich",
    procedure: "Open procedure",
    authority: "Canton of Zurich, Office for Information Technology",
    summary: "4-year framework contract · Lots 1 and 2",
    submission_deadline: "2026-11-19",
    forms: [
      form(),
      form({
        id: 2,
        title: "Annex 7 — Sanctions self-declaration (Art. 29c)",
        file_name: "Annex_7_Self-Declaration_Art29c_Ukraine_Ordinance.pdf",
        file_format: "pdf",
        field_counts: { fields: 10, yes_no: 0, signatures: 1 },
        estimated_fill_seconds: 25,
      }),
    ],
    ...overrides,
  };
}

export function tenderSummary(overrides: Partial<TenderSummary> = {}): TenderSummary {
  const { id, reference, title, submission_deadline } = tender();
  return { id, reference, title, submission_deadline, ...overrides };
}

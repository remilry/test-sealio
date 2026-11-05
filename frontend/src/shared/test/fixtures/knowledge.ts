import { readFileSync } from "node:fs";
import type { Schema } from "@/shared/api";

export type KnowledgeBase = Schema<"KnowledgeBase">;
export type KnowledgeDocument = Schema<"DocumentOut">;

export function knowledgeDocument(overrides: Partial<KnowledgeDocument> = {}): KnowledgeDocument {
  return {
    id: 1,
    name: "Commercial register extract",
    file_name: "01_commercial_register_extract.pdf",
    file_format: "pdf",
    pages: 2,
    status: "indexed",
    error: null,
    created_at: "2026-11-04T12:29:00Z",
    indexed_at: "2026-11-04T12:29:05Z",
    ...overrides,
  };
}

/** The demo company's annual report, a real Word document of `knowledge-base/documents/`. */
export function annualReportFile(): Uint8Array {
  return new Uint8Array(readFileSync("../knowledge-base/documents/09_annual_report_2024.docx"));
}

/** The seeded knowledge base (a few of its 11 documents), as returned by `GET /knowledge`. */
export function knowledgeBase(overrides: Partial<KnowledgeBase> = {}): KnowledgeBase {
  return {
    company_name: "Alpenlogic AG",
    documents: [
      knowledgeDocument(),
      knowledgeDocument({
        id: 9,
        name: "Annual report 2024",
        file_name: "09_annual_report_2024.docx",
        file_format: "docx",
        pages: null,
      }),
    ],
    last_indexed_at: "2026-11-04T12:29:05Z",
    ...overrides,
  };
}

import type { DocxLocator } from "./docx-locator";
import type { PdfBox } from "./locator";

export type ZoneTone =
  "auto" | "toCheck" | "empty" | "entered" | "signature" | "searching" | "writing";

/** The tones explained under the document, in this order (a searched zone explains itself). */
export const LEGEND = ["auto", "toCheck", "empty", "entered", "signature"] as const;

/** Where a field is on a PDF page. */
export type PdfPlace = {
  format: "pdf";
  page: number;
  box: PdfBox;
  fontSize: number;
  /** The placeholder marks printed in the field (dot leaders), hidden once it has a value. */
  placeholders: PdfBox[];
};

/** Where a field is in a Word document (the parser's locator). */
export type WordPlace = { format: "docx"; locator: DocxLocator };

/** A field drawn on the document: generic, the preview knows nothing of answers or rules. */
export type PreviewZone = {
  id: number;
  label: string;
  value: string | null;
  tone: ZoneTone;
  place: PdfPlace | WordPlace;
};

export type PdfZone = PreviewZone & { place: PdfPlace };

export const TONES: Record<ZoneTone, { zone: string; swatch: string }> = {
  auto: {
    zone: "bg-primary/10 ring-primary/45",
    swatch: "bg-primary/30",
  },
  toCheck: {
    zone: "bg-warning/12 ring-warning/55",
    swatch: "bg-warning/35",
  },
  entered: {
    zone: "bg-success/12 ring-success/50",
    swatch: "bg-success/30",
  },
  empty: {
    zone: "bg-[repeating-linear-gradient(135deg,color-mix(in_oklch,var(--destructive)_18%,transparent)_0_3px,transparent_3px_6px)] ring-destructive/40",
    swatch: "bg-destructive/25",
  },
  signature: {
    zone: "border border-dashed border-muted-foreground/60 bg-muted/40 ring-transparent",
    swatch: "bg-muted-foreground/25",
  },
  searching: {
    zone: "animate-pulse bg-primary/8 ring-primary/30",
    swatch: "bg-primary/15",
  },
  // A value the model is writing, not verified yet: greyed until its answer replaces it.
  writing: {
    zone: "bg-primary/8 italic ring-primary/30 text-black/50!",
    swatch: "bg-primary/15",
  },
};

"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { Document, Page, pdfjs } from "react-pdf";
import type { PageSize } from "./locator";

// Must be set in the module that renders react-pdf (see react-pdf's README).
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

// Canvas resolution relative to the page size in points; CSS then scales it to the column.
const RENDER_SCALE = 1.6;

/** The pages of a PDF, each with an overlay drawn in the same box (browser only: PDF.js). */
export default function PdfPages({
  fileUrl,
  pages,
  renderOverlay,
}: {
  fileUrl: string;
  pages: PageSize[];
  renderOverlay: (pageIndex: number) => ReactNode;
}) {
  const t = useTranslations("preview");
  return (
    <Document
      file={fileUrl}
      className="flex flex-col gap-4"
      loading={null}
      error={
        <p role="alert" className="text-sm text-destructive">
          {t("loadError")}
        </p>
      }
    >
      {pages.map((size, index) => (
        <div
          key={index}
          className="@container relative w-full overflow-hidden bg-white shadow-sm ring-1 ring-border [&_canvas]:h-auto! [&_canvas]:w-full!"
          style={{ aspectRatio: `${size.width} / ${size.height}` }}
        >
          <Page
            pageNumber={index + 1}
            width={size.width * RENDER_SCALE}
            renderTextLayer={false}
            renderAnnotationLayer={false}
            loading={null}
          />
          {renderOverlay(index)}
        </div>
      ))}
    </Document>
  );
}

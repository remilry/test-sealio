"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Document, Page, pdfjs } from "react-pdf";
import { Skeleton } from "@/shared/ui/skeleton";

// Must be set in the module that renders react-pdf (see react-pdf's README).
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

// Canvas width in pixels (A4 at ~1.6×); CSS then scales it to the column.
const RENDER_WIDTH = 952;

/** Every page of a PDF whose page count is only known once loaded (browser only: PDF.js). */
export default function PdfDocument({ fileUrl }: { fileUrl: string }) {
  const t = useTranslations("preview");
  const [pageCount, setPageCount] = useState<number | null>(null);
  return (
    <Document
      file={fileUrl}
      className="flex flex-col gap-4"
      onLoadSuccess={(pdf) => setPageCount(pdf.numPages)}
      loading={<Skeleton className="aspect-[595/842] w-full" />}
      error={
        <p role="alert" className="text-sm text-destructive">
          {t("documentLoadError")}
        </p>
      }
    >
      {Array.from({ length: pageCount ?? 0 }, (_, index) => (
        <div
          key={index}
          aria-label={t("page", { number: index + 1 })}
          className="w-full overflow-hidden bg-white shadow-sm ring-1 ring-border [&_canvas]:h-auto! [&_canvas]:w-full!"
        >
          <Page
            pageNumber={index + 1}
            width={RENDER_WIDTH}
            renderTextLayer={false}
            renderAnnotationLayer={false}
            loading={<Skeleton className="aspect-[595/842] w-full" />}
          />
        </div>
      ))}
    </Document>
  );
}

"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Document, Page, pdfjs } from "react-pdf";
import { Skeleton } from "@/shared/ui/skeleton";
import "react-pdf/dist/Page/TextLayer.css";
import { markedItemHtml } from "./quote-highlight";
import type { QuoteFocus } from "./zones";

// Must be set in the module that renders react-pdf (see react-pdf's README).
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

// Canvas width in pixels (A4 at ~1.6×); CSS then scales it to the column.
const RENDER_WIDTH = 952;

/**
 * Every page of a PDF whose page count is only known once loaded (browser only: PDF.js). With a
 * `focus`, its page is scrolled to once drawn and the quote is marked in its text.
 */
export default function PdfDocument({ fileUrl, focus }: { fileUrl: string; focus?: QuoteFocus }) {
  const t = useTranslations("preview");
  const [pageCount, setPageCount] = useState<number | null>(null);
  const focused = useRef<HTMLDivElement>(null);
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
      {Array.from({ length: pageCount ?? 0 }, (_, index) => {
        const quote = focus?.page === index ? focus.quote : null;
        return (
          <div
            key={index}
            ref={quote === null ? undefined : focused}
            aria-label={t("page", { number: index + 1 })}
            aria-current={quote === null ? undefined : "page"}
            className="relative w-full overflow-hidden bg-white shadow-sm ring-1 ring-border [&_canvas]:h-auto! [&_canvas]:w-full! [&_mark]:rounded-[2px] [&_mark]:bg-yellow-300/60 [&_mark]:text-transparent"
          >
            <Page
              pageNumber={index + 1}
              width={RENDER_WIDTH}
              renderTextLayer={quote !== null}
              customTextRenderer={
                quote === null ? undefined : ({ str }) => markedItemHtml(str, quote)
              }
              onRenderSuccess={
                quote === null
                  ? undefined
                  : () => focused.current?.scrollIntoView?.({ block: "start" })
              }
              renderAnnotationLayer={false}
              loading={<Skeleton className="aspect-[595/842] w-full" />}
            />
          </div>
        );
      })}
    </Document>
  );
}

"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { useTranslations } from "next-intl";
import { Document, Page, pdfjs } from "react-pdf";
import { Skeleton } from "@/shared/ui/skeleton";
import "react-pdf/dist/Page/TextLayer.css";
import { markedItemHtml, quoteItems } from "./quote-highlight";
import type { QuoteFocus } from "./zones";

// Must be set in the module that renders react-pdf (see react-pdf's README).
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

// Page width in pixels until the column is measured (A4 at ~1.6×); CSS then fits it.
const RENDER_WIDTH = 952;

/**
 * Every page of a PDF whose page count is only known once loaded (browser only: PDF.js). With a
 * `focus`, its page is scrolled to once drawn and the quote is marked in its text.
 */
export default function PdfDocument({ fileUrl, focus }: { fileUrl: string; focus?: QuoteFocus }) {
  const t = useTranslations("preview");
  const [pageCount, setPageCount] = useState<number | null>(null);
  const focused = useRef<HTMLDivElement>(null);
  // The text items of the focused page, once read: the quote is looked for in them.
  const [focusText, setFocusText] = useState<{ page: number; items: string[] } | null>(null);
  const marked =
    focus && focusText?.page === focus.page
      ? quoteItems(focusText.items, focus.quote)
      : new Set<number>();
  // Pages are drawn at the column's width: the text layer, where the quote is marked, is laid
  // out for that width and would drift from a canvas scaled by CSS.
  const column = useRef<HTMLDivElement>(null);
  const width = useWidth(column) || RENDER_WIDTH;
  return (
    <div ref={column}>
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
          const onFocus = quote !== null;
          return (
            <div
              key={index}
              ref={onFocus ? focused : undefined}
              aria-label={t("page", { number: index + 1 })}
              aria-current={onFocus ? "page" : undefined}
              className="relative w-full overflow-hidden bg-white shadow-sm ring-1 ring-border [&_canvas]:h-auto! [&_canvas]:w-full! [&_mark]:rounded-[2px] [&_mark]:bg-yellow-300/60 [&_mark]:text-transparent"
            >
              <Page
                pageNumber={index + 1}
                width={width}
                renderTextLayer={onFocus}
                onGetTextSuccess={
                  onFocus
                    ? ({ items }) =>
                        setFocusText({
                          page: index,
                          items: items.map((item) => ("str" in item ? item.str : "")),
                        })
                    : undefined
                }
                customTextRenderer={
                  onFocus
                    ? ({ str, itemIndex }) => markedItemHtml(str, marked.has(itemIndex))
                    : undefined
                }
                onRenderSuccess={
                  // The first page is already in sight, under the source's name.
                  onFocus && index > 0
                    ? () => focused.current?.scrollIntoView?.({ block: "start" })
                    : undefined
                }
                renderAnnotationLayer={false}
                loading={<Skeleton className="aspect-[595/842] w-full" />}
              />
            </div>
          );
        })}
      </Document>
    </div>
  );
}

/** The width of an element in CSS pixels, kept up to date (0 until measured). */
function useWidth(element: RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const target = element.current;
    if (!target || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    observer.observe(target);
    return () => observer.disconnect();
  }, [element]);
  return width;
}

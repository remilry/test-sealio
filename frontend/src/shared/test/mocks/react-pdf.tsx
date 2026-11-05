import { useEffect, type ReactNode } from "react";

/**
 * Test stand-in for react-pdf (aliased in vitest.config.mts): PDF.js needs canvas and a worker,
 * which jsdom lacks. Each page is a plain element; the field overlay around it stays real.
 */
export const pdfjs = { GlobalWorkerOptions: { workerSrc: "" }, version: "test" };

/** Pages every stubbed PDF reports once "loaded". */
export const STUB_PAGE_COUNT = 2;

export function Document({
  file,
  children,
  className,
  onLoadSuccess,
}: {
  file: string;
  children?: ReactNode;
  className?: string;
  onLoadSuccess?: (pdf: { numPages: number }) => void;
}) {
  useEffect(() => {
    onLoadSuccess?.({ numPages: STUB_PAGE_COUNT });
    // Loaded once per file, as react-pdf does.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file]);
  return (
    <div data-pdf-file={file} className={className}>
      {children}
    </div>
  );
}

export function Page({
  pageNumber,
  renderTextLayer,
}: {
  pageNumber: number;
  renderTextLayer?: boolean;
}) {
  // The text layer (where a quote is marked) is drawn only for the page that asks for it.
  return <div data-pdf-page={pageNumber} data-text-layer={renderTextLayer ? "" : undefined} />;
}

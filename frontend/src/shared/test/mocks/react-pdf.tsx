import type { ReactNode } from "react";

/**
 * Test stand-in for react-pdf (aliased in vitest.config.mts): PDF.js needs canvas and a worker,
 * which jsdom lacks. Each page is a plain element; the field overlay around it stays real.
 */
export const pdfjs = { GlobalWorkerOptions: { workerSrc: "" }, version: "test" };

export function Document({
  file,
  children,
  className,
}: {
  file: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div data-pdf-file={file} className={className}>
      {children}
    </div>
  );
}

export function Page({ pageNumber }: { pageNumber: number }) {
  return <div data-pdf-page={pageNumber} />;
}

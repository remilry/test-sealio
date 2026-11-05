"use client";

import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { Skeleton } from "@/shared/ui/skeleton";
import { WordDocument } from "./WordDocument";
import type { QuoteFocus } from "./zones";

// PDF.js only runs in the browser.
const PdfDocument = dynamic(() => import("./PdfDocument"), {
  ssr: false,
  loading: () => <Skeleton className="aspect-[595/842] w-full" />,
});

/**
 * A source document, whole, opened where a quote is: at its page for a PDF (the quote marked in
 * the page's text), at the quote itself for a Word document.
 */
export function SourceViewer({
  fileUrl,
  fileFormat,
  label,
  focus,
}: {
  fileUrl: string;
  fileFormat: "pdf" | "docx";
  label: string;
  focus: QuoteFocus;
}) {
  const t = useTranslations("preview");
  return (
    <section aria-label={t("documentLabel", { name: label })}>
      {fileFormat === "docx" ? (
        <WordDocument
          fileUrl={fileUrl}
          zones={[]}
          selectedId={null}
          onSelect={() => {}}
          focus={focus}
        />
      ) : (
        // A new file is a new document: its pages are loaded again.
        <PdfDocument key={fileUrl} fileUrl={fileUrl} focus={focus} />
      )}
    </section>
  );
}

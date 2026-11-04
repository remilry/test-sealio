"use client";

import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { Skeleton } from "@/shared/ui/skeleton";

// PDF.js only runs in the browser.
const PdfDocument = dynamic(() => import("./PdfDocument"), {
  ssr: false,
  loading: () => <Skeleton className="aspect-[595/842] w-full" />,
});

/** Read-only view of any PDF, page after page (a company document, for instance). */
export function PdfViewer({ fileUrl, label }: { fileUrl: string; label: string }) {
  const t = useTranslations("preview");
  return (
    <section aria-label={t("documentLabel", { name: label })}>
      <PdfDocument fileUrl={fileUrl} />
    </section>
  );
}

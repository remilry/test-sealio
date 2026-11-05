"use client";

import { useTranslations } from "next-intl";
import { WordDocument } from "./WordDocument";

/** Read-only view of a Word document, page after page (a form before it is filled, for instance). */
export function WordViewer({ fileUrl, label }: { fileUrl: string; label: string }) {
  const t = useTranslations("preview");
  return (
    <section aria-label={t("documentLabel", { name: label })}>
      <WordDocument fileUrl={fileUrl} zones={[]} selectedId={null} onSelect={() => {}} />
    </section>
  );
}

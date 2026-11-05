"use client";

import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { cn } from "@/shared/lib/utils";
import { Skeleton } from "@/shared/ui/skeleton";
import { boxToCss, fontSizeToCss, type PageSize } from "./locator";
import { WordDocument } from "./WordDocument";
import { LEGEND, TONES, type PdfZone, type PreviewZone } from "./zones";

// PDF.js only runs in the browser.
const PdfPages = dynamic(() => import("./PdfPages"), {
  ssr: false,
  loading: () => <Skeleton className="aspect-[595/842] w-full" />,
});

/** The original form, with each field highlighted where its answer goes, kept in sync with the list. */
export function DocumentPreview({
  fileUrl,
  fileFormat,
  pages,
  zones,
  selectedId,
  onSelect,
}: {
  fileUrl: string;
  fileFormat: "pdf" | "docx";
  pages: PageSize[];
  zones: PreviewZone[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const t = useTranslations("preview");
  return (
    <section aria-label={t("label")} className="flex flex-col gap-3">
      <ul aria-label={t("legend")} className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        {LEGEND.map((tone) => (
          <li key={tone} className="flex items-center gap-1.5">
            <span aria-hidden className={cn("h-2 w-3.5 rounded-xs", TONES[tone].swatch)} />
            {t(`tone.${tone}`)}
          </li>
        ))}
      </ul>
      {fileFormat === "docx" ? (
        <WordDocument fileUrl={fileUrl} zones={zones} selectedId={selectedId} onSelect={onSelect} />
      ) : (
        <PdfPreview
          fileUrl={fileUrl}
          pages={pages}
          zones={zones.filter((zone): zone is PdfZone => zone.place.format === "pdf")}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      )}
    </section>
  );
}

function PdfPreview({
  fileUrl,
  pages,
  zones,
  selectedId,
  onSelect,
}: {
  fileUrl: string;
  pages: PageSize[];
  zones: PdfZone[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  return (
    <PdfPages
      fileUrl={fileUrl}
      pages={pages}
      renderOverlay={(pageIndex) => {
        const onPage = zones.filter((zone) => zone.place.page === pageIndex);
        return (
          <>
            {onPage.map((zone) => (
              <PlaceholderMasks key={zone.id} zone={zone} page={pages[pageIndex]} />
            ))}
            {onPage.map((zone) => (
              <Zone
                key={zone.id}
                zone={zone}
                page={pages[pageIndex]}
                selected={zone.id === selectedId}
                onSelect={onSelect}
              />
            ))}
          </>
        );
      }}
    />
  );
}

/** Paper over the dot leaders of a filled field, as the export removes them: dots only show while empty. */
function PlaceholderMasks({ zone, page }: { zone: PdfZone; page: PageSize }) {
  if (!zone.value) return null;
  return zone.place.placeholders.map((box, index) => (
    <div
      key={index}
      aria-hidden
      data-placeholder-of={zone.id}
      style={boxToCss(box, page, 0)}
      className="pointer-events-none absolute bg-white"
    />
  ));
}

function Zone({
  zone,
  page,
  selected,
  onSelect,
}: {
  zone: PdfZone;
  page: PageSize;
  selected: boolean;
  onSelect: (id: number) => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (selected) ref.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [selected]);

  return (
    <button
      ref={ref}
      type="button"
      data-field-id={zone.id}
      data-tone={zone.tone}
      aria-label={zone.label}
      aria-pressed={selected}
      onClick={() => onSelect(zone.id)}
      style={{
        ...boxToCss(zone.place.box, page),
        fontSize: fontSizeToCss(zone.place.fontSize, page),
      }}
      className={cn(
        "absolute flex cursor-pointer items-end overflow-hidden rounded-[2px] px-[0.3cqw] pb-[0.25cqw] text-left leading-none whitespace-nowrap text-black ring-1 transition-shadow",
        TONES[zone.tone].zone,
        selected && "ring-2 ring-primary",
      )}
    >
      {zone.value && <span className="truncate">{zone.value}</span>}
    </button>
  );
}

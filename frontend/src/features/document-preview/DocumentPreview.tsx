"use client";

import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { cn } from "@/shared/lib/utils";
import { Skeleton } from "@/shared/ui/skeleton";
import { boxToCss, fontSizeToCss, type PageSize, type PdfBox } from "./locator";

// PDF.js only runs in the browser.
const PdfPages = dynamic(() => import("./PdfPages"), {
  ssr: false,
  loading: () => <Skeleton className="aspect-[595/842] w-full" />,
});

export type ZoneTone = "auto" | "toCheck" | "empty" | "entered" | "signature" | "searching";

/** The tones explained under the document, in this order (a searched zone explains itself). */
const LEGEND = ["auto", "toCheck", "empty", "entered", "signature"] as const;

/** A field drawn on the document: generic, the preview knows nothing of answers or rules. */
export type PreviewZone = {
  id: number;
  label: string;
  page: number;
  box: PdfBox;
  fontSize: number;
  /** The placeholder marks printed in the field (dot leaders), hidden once it has a value. */
  placeholders: PdfBox[];
  value: string | null;
  tone: ZoneTone;
};

const TONES: Record<ZoneTone, { zone: string; swatch: string }> = {
  auto: {
    zone: "bg-primary/10 ring-primary/45",
    swatch: "bg-primary/30",
  },
  toCheck: {
    zone: "bg-warning/12 ring-warning/55",
    swatch: "bg-warning/35",
  },
  entered: {
    zone: "bg-success/12 ring-success/50",
    swatch: "bg-success/30",
  },
  empty: {
    zone: "bg-[repeating-linear-gradient(135deg,color-mix(in_oklch,var(--destructive)_18%,transparent)_0_3px,transparent_3px_6px)] ring-destructive/40",
    swatch: "bg-destructive/25",
  },
  signature: {
    zone: "border border-dashed border-muted-foreground/60 bg-muted/40 ring-transparent",
    swatch: "bg-muted-foreground/25",
  },
  searching: {
    zone: "animate-pulse bg-primary/8 ring-primary/30",
    swatch: "bg-primary/15",
  },
};

/** The original form, with each field highlighted where its answer goes, kept in sync with the list. */
export function DocumentPreview({
  fileUrl,
  pages,
  zones,
  selectedId,
  onSelect,
}: {
  fileUrl: string;
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
      <PdfPages
        fileUrl={fileUrl}
        pages={pages}
        renderOverlay={(pageIndex) => {
          const onPage = zones.filter((zone) => zone.page === pageIndex);
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
    </section>
  );
}

/** Paper over the dot leaders of a filled field, as the export removes them: dots only show while empty. */
function PlaceholderMasks({ zone, page }: { zone: PreviewZone; page: PageSize }) {
  if (!zone.value) return null;
  return zone.placeholders.map((box, index) => (
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
  zone: PreviewZone;
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
      style={{ ...boxToCss(zone.box, page), fontSize: fontSizeToCss(zone.fontSize, page) }}
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

"use client";

import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { cn } from "@/shared/lib/utils";
import { Skeleton } from "@/shared/ui/skeleton";
import { boxToCss, fontSizeToCss, type PageSize, type PdfBox } from "./locator";

// PDF.js only runs in the browser.
const PdfPages = dynamic(() => import("./PdfPages"), {
  ssr: false,
  loading: () => <Skeleton className="aspect-[595/842] w-full" />,
});

export type ZoneTone = "entered" | "empty" | "signature";

/** A field drawn on the document: generic, the preview knows nothing of answers or rules. */
export type PreviewZone = {
  id: number;
  label: string;
  page: number;
  box: PdfBox;
  fontSize: number;
  value: string | null;
  tone: ZoneTone;
};

const TONES: Record<ZoneTone, { label: string; zone: string; swatch: string }> = {
  entered: {
    label: "Entered by you",
    zone: "bg-success/12 ring-success/50",
    swatch: "bg-success/30",
  },
  empty: {
    label: "Empty",
    zone: "bg-[repeating-linear-gradient(135deg,color-mix(in_oklch,var(--destructive)_18%,transparent)_0_3px,transparent_3px_6px)] ring-destructive/40",
    swatch: "bg-destructive/25",
  },
  signature: {
    label: "Sign by hand",
    zone: "border border-dashed border-muted-foreground/60 bg-muted/40 ring-transparent",
    swatch: "bg-muted-foreground/25",
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
  return (
    <section aria-label="Form preview" className="flex flex-col gap-3">
      <ul aria-label="Legend" className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        {Object.values(TONES).map((tone) => (
          <li key={tone.label} className="flex items-center gap-1.5">
            <span aria-hidden className={cn("h-2 w-3.5 rounded-xs", tone.swatch)} />
            {tone.label}
          </li>
        ))}
      </ul>
      <PdfPages
        fileUrl={fileUrl}
        pages={pages}
        renderOverlay={(pageIndex) =>
          zones
            .filter((zone) => zone.page === pageIndex)
            .map((zone) => (
              <Zone
                key={zone.id}
                zone={zone}
                page={pages[pageIndex]}
                selected={zone.id === selectedId}
                onSelect={onSelect}
              />
            ))
        }
      />
    </section>
  );
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
      {zone.value && (
        // Hides the dot leaders under the value, as the export does.
        <span className="truncate bg-white/90">{zone.value}</span>
      )}
    </button>
  );
}

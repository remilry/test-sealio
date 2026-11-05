"use client";

import { useEffect, useLayoutEffect, useRef, useState, type MouseEvent } from "react";
import { renderAsync } from "docx-preview";
import { useTranslations } from "next-intl";
import { cn } from "@/shared/lib/utils";
import { Skeleton } from "@/shared/ui/skeleton";
import { useDocumentFile } from "./document-preview.queries";
import { findParagraph, writePreviewValue } from "./docx-locator";
import { TONES, type PreviewZone, type WordPlace } from "./zones";

const ZONE = "cursor-pointer rounded-[2px] ring-1 transition-shadow";
const SELECTED = "ring-2 ring-primary";
/** Classes a zone was given, to take them back at the next decoration. */
const APPLIED = "data-zone-classes";

type WordZone = PreviewZone & { place: WordPlace };

/**
 * A Word document rendered in the page (docx-preview), each field highlighted where the export
 * writes its value, the value shown there as it is typed. The document is rendered once per file;
 * the zones are then drawn onto it at every change.
 */
export function WordDocument({
  fileUrl,
  zones,
  selectedId,
  onSelect,
}: {
  fileUrl: string;
  zones: PreviewZone[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const t = useTranslations("preview");
  const file = useDocumentFile(fileUrl);
  const container = useRef<HTMLDivElement>(null);
  const [rendered, setRendered] = useState<Blob | null>(null);
  const [renderFailed, setRenderFailed] = useState(false);

  useEffect(() => {
    const target = container.current;
    if (!file.data || !target) return;
    let current = true;
    renderAsync(file.data, target, undefined, {
      inWrapper: false,
      ignoreLastRenderedPageBreak: false,
      className: "docx",
    })
      .then(() => current && setRendered(file.data))
      .catch(() => current && setRenderFailed(true));
    return () => {
      current = false;
    };
  }, [file.data]);

  const ready = rendered !== null && rendered === file.data;
  useLayoutEffect(() => {
    const root = container.current;
    if (!ready || !root) return;
    drawZones(
      root,
      zones.filter((zone): zone is WordZone => zone.place.format === "docx"),
      selectedId,
    );
  }, [ready, zones, selectedId]);

  useEffect(() => {
    if (!ready || selectedId === null) return;
    container.current
      ?.querySelector(`[data-field-id="${selectedId}"]`)
      ?.scrollIntoView?.({ block: "center", behavior: "smooth" });
  }, [ready, selectedId]);

  const select = (event: MouseEvent<HTMLDivElement>) => {
    const zone = (event.target as Element).closest("[data-field-id]");
    if (zone) onSelect(Number(zone.getAttribute("data-field-id")));
  };

  if (file.isError || renderFailed) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {t("documentLoadError")}
      </p>
    );
  }
  return (
    <>
      {!ready && <Skeleton className="aspect-[595/842] w-full" />}
      {/* docx-preview owns this element's children; React never renders into it. */}
      <div
        ref={container}
        onClick={select}
        className={cn(
          "flex flex-col gap-4 text-black [&_section.docx]:bg-white [&_section.docx]:shadow-sm [&_section.docx]:ring-1 [&_section.docx]:ring-border",
          "[&_[data-preview-empty]]:inline-block [&_[data-preview-empty]]:h-[1em] [&_[data-preview-empty]]:min-w-16 [&_[data-preview-empty]]:align-middle",
          !ready && "hidden",
        )}
      />
    </>
  );
}

/** Write each zone's value into the rendered document and mark where each field is. */
function drawZones(root: HTMLElement, zones: WordZone[], selectedId: number | null) {
  root.querySelectorAll<HTMLElement>("[data-field-id]").forEach(clearZone);
  for (const zone of zones) {
    const paragraph = findParagraph(root, zone.place.locator);
    if (!paragraph) continue;
    const value = zone.tone === "signature" ? null : zone.value;
    const element = writePreviewValue(paragraph, zone.place.locator, value);
    const classes = cn(ZONE, TONES[zone.tone].zone, zone.id === selectedId && SELECTED)
      .split(" ")
      .filter(Boolean);
    element.classList.add(...classes);
    element.setAttribute(APPLIED, classes.join(" "));
    element.setAttribute("data-field-id", String(zone.id));
    element.setAttribute("data-tone", zone.tone);
    element.setAttribute("aria-label", zone.label);
    element.setAttribute("aria-pressed", String(zone.id === selectedId));
  }
}

function clearZone(element: HTMLElement) {
  element.classList.remove(...(element.getAttribute(APPLIED) ?? "").split(" ").filter(Boolean));
  for (const name of [APPLIED, "data-field-id", "data-tone", "aria-label", "aria-pressed"]) {
    element.removeAttribute(name);
  }
}

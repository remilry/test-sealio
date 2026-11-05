"use client";

import { useEffect, useLayoutEffect, useRef, useState, type MouseEvent } from "react";
import { parseAsync, renderDocument } from "docx-preview";
import { useTranslations } from "next-intl";
import { cn } from "@/shared/lib/utils";
import { Skeleton } from "@/shared/ui/skeleton";
import { useDocumentFile } from "./document-preview.queries";
import { markPageFields, numberPages } from "./docx-fields";
import { withFontFallbacks, type DocumentFont } from "./docx-fonts";
import { showImages } from "./docx-images";
import { findParagraph, writePreviewValue } from "./docx-locator";
import { paginate } from "./docx-pages";
import { withWordLineSpacing } from "./docx-spacing";
import { TONES, type PreviewZone, type WordPlace } from "./zones";

const ZONE = "cursor-pointer rounded-[2px] ring-1 transition-shadow";
const SELECTED = "ring-2 ring-primary";
/** Classes a zone was given, to take them back at the next decoration. */
const APPLIED = "data-zone-classes";

type WordZone = PreviewZone & { place: WordPlace };

/**
 * A Word document rendered in the page (docx-preview), each field highlighted where the export
 * writes its value, the value shown there as it is typed. The document is rendered once per file;
 * the zones are then drawn onto it at every change. Pages break as on paper (`paginate`), not at
 * the marks Word leaves where it last broke them: those split a paragraph in two, and the
 * paragraphs would no longer be counted as the export counts them.
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
    const blob = file.data;
    if (!blob || !target) return;
    // A rendering that ends after a newer one (a new file, React running effects twice) is dropped.
    let current = true;
    renderPages(blob, target, () => current)
      .then((done) => done && setRendered(blob))
      .catch(() => current && setRenderFailed(true));
    return () => {
      current = false;
    };
  }, [file.data]);

  const ready = rendered !== null && rendered === file.data;

  // Pages keep their real width (an A4 page is ~794 px): narrower than that, they are scaled
  // down to the column (never up), the text still laid out as on paper.
  useEffect(() => {
    const root = container.current;
    if (!ready || !root) return;
    return fitToWidth(root);
  }, [ready]);
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
    <div className="relative">
      {!ready && <Skeleton className="aspect-[595/842] w-full" />}
      {/* docx-preview owns this element's children; React never renders into it. While it renders,
          it is laid out but unseen: its pages are measured to break them as on paper. */}
      <div
        ref={container}
        onClick={select}
        className={cn(
          "text-black [&_section.docx]:bg-white [&_section.docx]:shadow-sm [&_section.docx]:ring-1 [&_section.docx]:ring-border",
          "[&_[data-preview-empty]]:inline-block [&_[data-preview-empty]]:h-[1em] [&_[data-preview-empty]]:min-w-16 [&_[data-preview-empty]]:align-middle",
          !ready && "pointer-events-none invisible absolute inset-x-0 top-0",
        )}
      />
    </div>
  );
}

const RENDER_OPTIONS = { inWrapper: false, className: "docx" };

/**
 * Render the document apart, then, if still wanted, put it in `target` and lay it out as on paper:
 * the document's fallback fonts, pages of the paper's height, its images. False when dropped.
 */
async function renderPages(blob: Blob, target: HTMLElement, isCurrent: () => boolean) {
  const document_ = await parseAsync(blob, RENDER_OPTIONS);
  markPageFields(document_);
  const nodes = await renderDocument(document_, RENDER_OPTIONS);
  if (!isCurrent()) return false;
  const pages = document.createElement("div");
  pages.className = "flex flex-col gap-4";
  pages.append(...nodes);
  withFontFallbacks(pages, (document_.fontTablePart?.fonts ?? []) as DocumentFont[]);
  withWordLineSpacing(pages);
  target.replaceChildren(pages);
  paginate(pages);
  numberPages(pages);
  void showImages(pages);
  return true;
}

/** Scale the rendered pages to `root`'s width, now and when it changes; returns the cleanup. */
function fitToWidth(root: HTMLElement): (() => void) | undefined {
  const pages = root.firstElementChild;
  if (!(pages instanceof HTMLElement)) return;
  const width = pageWidth(pages);
  if (!width) return;
  const fit = () => {
    pages.style.zoom = String(Math.min(1, root.clientWidth / width));
  };
  fit();
  if (typeof ResizeObserver === "undefined") return;
  const observer = new ResizeObserver(fit);
  observer.observe(root);
  return () => observer.disconnect();
}

/** The widest page, in CSS pixels, as docx-preview sizes it (`width: 595.3pt`). */
function pageWidth(pages: HTMLElement): number {
  const widths = [...pages.querySelectorAll<HTMLElement>("section.docx")].map((section) => {
    const match = /^([\d.]+)(pt|px)$/.exec(section.style.width);
    if (!match) return 0;
    return match[2] === "pt" ? (Number(match[1]) * 4) / 3 : Number(match[1]);
  });
  return Math.max(0, ...widths);
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

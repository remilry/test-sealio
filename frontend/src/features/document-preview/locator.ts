/** A rectangle in PDF points, origin top-left (as the back's PdfLocator). */
export type PdfBox = { x0: number; y0: number; x1: number; y1: number };
export type PageSize = { width: number; height: number };

/**
 * PDF points → CSS percentages of the rendered page, so the overlay follows the page at any width.
 * A little padding makes the zone easier to see and click than the bare text line.
 */
export function boxToCss(box: PdfBox, page: PageSize, padding = 2) {
  const percent = (value: number, total: number) => `${(value / total) * 100}%`;
  return {
    left: percent(box.x0 - padding, page.width),
    top: percent(box.y0 - padding, page.height),
    width: percent(box.x1 - box.x0 + 2 * padding, page.width),
    height: percent(box.y1 - box.y0 + 2 * padding, page.height),
  };
}

/** A font size in points → CSS, relative to the rendered page width (`cqw` of the page container). */
export function fontSizeToCss(fontSize: number, page: PageSize) {
  return `${(fontSize / page.width) * 100}cqw`;
}

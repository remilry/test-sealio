/** A font of the document's font table, as docx-preview parses it (`fontTablePart.fonts`). */
export type DocumentFont = { name: string; altName?: string; family?: string };

/** The CSS generic family of a Word font family (w:family). */
const GENERIC: Record<string, string> = {
  swiss: "sans-serif",
  roman: "serif",
  modern: "monospace",
};

/**
 * docx-preview writes only the document's font names: one not installed falls back to the
 * browser's default (a serif), which changes the line lengths and the page breaks. Each gets the
 * fallbacks the document itself declares: its alternate name, then its kind (sans-serif…).
 */
export function withFontFallbacks(root: HTMLElement, fonts: DocumentFont[]): void {
  const byName = new Map(fonts.map((font) => [font.name.toLowerCase(), font]));
  for (const element of root.querySelectorAll<HTMLElement>("[style*='font-family']")) {
    const declared = element.style.fontFamily;
    const first = declared
      .split(",")[0]
      .trim()
      .replace(/^["']|["']$/g, "");
    const font = byName.get(first.toLowerCase());
    if (!font) continue;
    const fallbacks = [font.altName, font.family && GENERIC[font.family]].filter(
      (name): name is string => Boolean(name) && !declared.includes(name as string),
    );
    if (fallbacks.length) element.style.fontFamily = [declared, ...fallbacks].join(", ");
  }
}

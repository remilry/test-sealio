/** Word's single line spacing, as a share of the font size (Arial, Helvetica, Calibri: ~1.15). */
const SINGLE_LINE = "1.15em";

/**
 * docx-preview renders an "at least N" line spacing (w:lineRule="atLeast") as a single line plus
 * N; Word uses the larger of the two. The sum makes every such line far too tall (the Annex 4 has
 * them in all its tables), and the pages too long.
 */
export function withWordLineSpacing(root: HTMLElement): void {
  for (const element of root.querySelectorAll<HTMLElement>("[style*='line-height']")) {
    const match = /^calc\(100% \+ ([\d.]+(?:pt|px))\)$/.exec(element.style.lineHeight);
    if (match) element.style.lineHeight = `max(${SINGLE_LINE}, ${match[1]})`;
  }
}

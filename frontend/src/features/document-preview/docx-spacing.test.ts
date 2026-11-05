import { withWordLineSpacing } from "./docx-spacing";

describe("line spacing of a rendered Word document", () => {
  test("an 'at least' spacing is the larger of a single line and its minimum, not their sum", () => {
    const root = document.createElement("div");
    root.innerHTML =
      `<p style="line-height: calc(100% + 15pt)">At least</p>` +
      `<p style="line-height: 1.15">Multiple</p><p style="line-height: 12pt">Exactly</p>`;

    withWordLineSpacing(root);

    const [atLeast, multiple, exactly] = [...root.querySelectorAll("p")].map(
      (p) => p.style.lineHeight,
    );
    // (15pt, which the browser may have written as 20px)
    expect(atLeast).toMatch(/^max\(1\.15em, (15pt|20px)\)$/);
    expect(multiple).toBe("1.15");
    expect(exactly).toBe("12pt");
  });
});

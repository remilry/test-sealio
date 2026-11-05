import { withFontFallbacks } from "./docx-fonts";

describe("fonts of a rendered Word document", () => {
  test("fall back on what the document names, then on the font's kind", () => {
    const root = document.createElement("div");
    root.innerHTML =
      `<span style='font-family: "HelveticaNeueLT Com 55 Roman"'>A</span>` +
      `<span style='font-family: Cambria'>B</span><span style='font-family: Unknown'>C</span>`;

    withFontFallbacks(root, [
      { name: "HelveticaNeueLT Com 55 Roman", altName: "Arial", family: "swiss" },
      { name: "Cambria", family: "roman" },
    ]);

    const [a, b, c] = [...root.querySelectorAll("span")].map((span) => span.style.fontFamily);
    expect(a).toBe('"HelveticaNeueLT Com 55 Roman", Arial, sans-serif');
    expect(b).toBe("Cambria, serif");
    expect(c).toBe("Unknown");
  });
});

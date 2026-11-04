import { boxToCss, fontSizeToCss } from "./locator";

const A4 = { width: 595, height: 842 };

describe("PDF locator → CSS", () => {
  it("places a box as percentages of the page, so it scales with the page", () => {
    expect(boxToCss({ x0: 119, y0: 421, x1: 297.5, y1: 431.5 }, A4, 0)).toEqual({
      left: "20%",
      top: "50%",
      width: "30%",
      height: `${(10.5 / 842) * 100}%`,
    });
  });

  it("pads the box on every side", () => {
    const css = boxToCss({ x0: 100, y0: 100, x1: 200, y1: 110 }, { width: 1000, height: 1000 }, 5);

    expect(css).toEqual({ left: "9.5%", top: "9.5%", width: "11%", height: "2%" });
  });

  it("scales the font size with the page width", () => {
    expect(fontSizeToCss(10, { width: 500, height: 800 })).toBe("2cqw");
  });
});

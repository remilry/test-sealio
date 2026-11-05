import { markPageFields, numberPages } from "./docx-fields";

/** A run of a parsed document (docx-preview's tree), with a field's parts. */
type Node = { type: string; text?: string; charType?: string };
const run = (...children: Node[]) => ({ type: "run", children });
const text = (value: string) => ({ type: "text", text: value });
const field = (charType: "begin" | "separate" | "end") => ({ type: "complexField", charType });
const instruction = (value: string) => ({ type: "instruction", text: value });

describe("page numbers of a rendered Word document", () => {
  test("each page shows its own number and the page count", () => {
    // Given a footer "Page <PAGE> of <NUMPAGES>", Word's last results being 3 and 4
    const footer = {
      type: "paragraph",
      children: [
        run(text("Page ")),
        run(field("begin")),
        run(instruction(" PAGE ")),
        run(field("separate")),
        run(text("3")),
        run(field("end")),
        run(text(" of ")),
        run(field("begin")),
        run(instruction(" NUMPAGES \\* MERGEFORMAT ")),
        run(field("separate")),
        run(text("4")),
        run(field("end")),
      ],
    };
    const parsed = { parts: [{ rootElement: { type: "footer", children: [footer] } }] };

    // When the fields are marked, rendered on two pages, then numbered
    markPageFields(parsed);
    const shown = footer.children
      .flatMap((r) => r.children)
      .filter((c) => c.type === "text")
      .map((c) => c.text)
      .join("");
    const root = document.createElement("div");
    root.innerHTML = [1, 2]
      .map(() => `<section class="docx"><article></article><footer>${shown}</footer></section>`)
      .join("");
    numberPages(root);

    // Then each page says where it is
    expect([...root.querySelectorAll("footer")].map((f) => f.textContent)).toEqual([
      "Page 1 of 2",
      "Page 2 of 2",
    ]);
  });

  test("other fields keep the result Word saved", () => {
    const paragraph = {
      type: "paragraph",
      children: [
        run(field("begin")),
        run(instruction(" DATE ")),
        run(field("separate")),
        run(text("5.11.2026")),
        run(field("end")),
      ],
    };

    markPageFields({ parts: [{ rootElement: { type: "header", children: [paragraph] } }] });

    expect(paragraph.children[3].children[0]).toEqual(text("5.11.2026"));
  });
});

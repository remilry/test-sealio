import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { handlers, renderScreen, server } from "@/shared/test";
import {
  annex7,
  answer,
  fillState,
  form as formSummary,
  tender,
  type FillState,
} from "@/shared/test/fixtures";
import { LiveFillScreen } from "./LiveFillScreen";

const fieldList = () => within(screen.getByRole("list", { name: "Fields" }));
const preview = () => screen.getByRole("region", { name: "Form preview" });
/** The zone drawn on the document for a field (the only place where data-field-id is used). */
const zone = (fieldId: number) =>
  preview().querySelector<HTMLButtonElement>(`[data-field-id="${fieldId}"]`)!;

/** The back keeps the answers it receives and returns the new fill state. */
function backWithAnswers(initial: FillState = fillState()) {
  let state = initial;
  const saved = handlers.saveField(2, (fieldId, { value }) => {
    const others = state.answers.filter((a) => a.field_id !== fieldId);
    state = fillState([...others, answer(fieldId, value?.trim() || null, "2026-11-03T13:45:00Z")]);
    return state;
  });
  server.use(handlers.answers(2, state), saved.handler);
  return saved;
}

function given(form = annex7(), answers: FillState = fillState()) {
  server.use(handlers.form(form), handlers.tender(tender()));
  const saved = backWithAnswers(answers);
  const user = userEvent.setup();
  renderScreen(<LiveFillScreen formId={2} />);
  return { saved, user };
}

describe("Live fill (manual)", () => {
  it("lists every detected field in reading order, the signature included", async () => {
    // Given the parsed Annex 7
    given();

    // When the form opens, then its 10 fields are listed in order
    const items = await screen.findAllByRole("listitem", { name: /./ });
    const fields = items.filter(
      (item) => item.closest("ol")?.getAttribute("aria-label") === "Fields",
    );
    expect(fields.map((item) => item.getAttribute("aria-label"))).toEqual([
      "Project number/project title/project name",
      "Name of the contracting authority",
      "Name and legal form",
      "Business address",
      "Contact person",
      "Telephone",
      "E-mail",
      "Place and date",
      "First name(s) and surname(s)",
      "Signature(s)",
    ]);
    // And the signature cannot be typed in: it is signed by hand
    const signature = within(fieldList().getByRole("listitem", { name: "Signature(s)" }));
    expect(signature.queryByRole("textbox")).not.toBeInTheDocument();
    expect(signature.getByText(/Sign by hand after export/)).toBeInTheDocument();
  });

  it("shows the original form with each field highlighted where its answer goes", async () => {
    // Given the parsed Annex 7
    given();

    // When the form opens
    await screen.findByRole("heading", { name: "9 fields to fill" });

    // Then the original PDF is rendered with one zone per field, placed from the parser's box
    expect(preview().querySelector("[data-pdf-file]")).toHaveAttribute(
      "data-pdf-file",
      "http://localhost:8000/forms/2/file",
    );
    expect(preview().querySelectorAll("[data-field-id]")).toHaveLength(10);
    expect(zone(6)).toHaveAccessibleName("Telephone");
    expect(zone(6).style.left).toBe(`${((143.9 - 2) / 595.3) * 100}%`);
    expect(within(preview()).getByText("Sign by hand")).toBeInTheDocument();
  });

  it("shows where I am: tender, form, how many fields are filled", async () => {
    // Given a form with two fields already filled
    given(annex7(), fillState([answer(3, "Alpenlogic AG"), answer(6, "+41 44 512 38 00")]));

    // When it opens
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Annex 7 — Sanctions self-declaration (Art. 29c)",
      }),
    ).toBeInTheDocument();

    // Then the breadcrumb, the counter and the values are shown
    const breadcrumb = within(screen.getByRole("navigation", { name: "Breadcrumb" }));
    expect(
      await breadcrumb.findByText("Cloud Platform Services – Canton of Zurich"),
    ).toBeInTheDocument();
    expect(screen.getByText("2 / 9 filled · 7 empty")).toBeInTheDocument();
    expect(fieldList().getByRole("textbox", { name: "Name and legal form" })).toHaveValue(
      "Alpenlogic AG",
    );
    expect(within(zone(3)).getByText("Alpenlogic AG")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the tender" })).toHaveAttribute(
      "href",
      "/tenders/1",
    );
  });

  it("saves what I type when I leave the field, and shows it on the form", async () => {
    // Given an empty form
    const { saved, user } = given();
    const telephone = await screen.findByRole("textbox", { name: "Telephone" });

    // When I type a phone number and leave the field
    await user.type(telephone, "  +41 44 512 38 00 ");
    await user.tab();

    // Then the back receives it and the value appears on the document
    await waitFor(() =>
      expect(saved.requests).toEqual([{ fieldId: 6, value: "+41 44 512 38 00" }]),
    );
    expect(await within(zone(6)).findByText("+41 44 512 38 00")).toBeInTheDocument();
    expect(await screen.findByText("1 / 9 filled · 8 empty")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Saved");
    const card = within(fieldList().getByRole("listitem", { name: "Telephone" }));
    expect(card.getByText("Entered by you · 14:45")).toBeInTheDocument();
  });

  it("does not save a field I only passed through", async () => {
    // Given a form with a saved telephone number
    const { saved, user } = given(annex7(), fillState([answer(6, "+41 44 512 38 00")]));

    // When I go through the field without changing it
    await user.click(await screen.findByRole("textbox", { name: "Telephone" }));
    await user.tab();

    // Then nothing is sent
    expect(saved.requests).toEqual([]);
  });

  it("Enter saves the value once and moves on to the next field", async () => {
    // Given an empty form
    const { saved, user } = given();

    // When I type a value in "Contact person" and press Enter
    await user.type(
      await screen.findByRole("textbox", { name: "Contact person" }),
      "Marc Keller{Enter}",
    );

    // Then it is saved once and the cursor is in "Telephone"
    await waitFor(() => expect(saved.requests).toEqual([{ fieldId: 5, value: "Marc Keller" }]));
    expect(screen.getByRole("textbox", { name: "Telephone" })).toHaveFocus();
    expect(fieldList().getByRole("listitem", { name: "Telephone" })).toHaveAttribute(
      "aria-current",
      "true",
    );
  });

  it("clearing a value leaves the field empty", async () => {
    // Given a saved e-mail
    const { saved, user } = given(annex7(), fillState([answer(7, "info@alpenlogic.ch")]));

    // When I clear it and leave the field
    await user.clear(await screen.findByRole("textbox", { name: "E-mail" }));
    await user.tab();

    // Then the back is told the field is empty, and the document shows it empty again
    await waitFor(() => expect(saved.requests).toEqual([{ fieldId: 7, value: null }]));
    await waitFor(() => expect(within(zone(7)).queryByText("info@alpenlogic.ch")).toBeNull());
    expect(await screen.findByText("0 / 9 filled · 9 empty")).toBeInTheDocument();
  });

  it("clicking a field on the document puts me in its input", async () => {
    // Given the form is open
    const { user } = given();
    await screen.findByRole("textbox", { name: "E-mail" });

    // When I click the e-mail zone on the document
    await user.click(zone(7));

    // Then the e-mail input has the focus, and the zone shows as selected
    expect(screen.getByRole("textbox", { name: "E-mail" })).toHaveFocus();
    expect(zone(7)).toHaveAttribute("aria-pressed", "true");
  });

  it("selects the first empty field when the form opens", async () => {
    // Given the first two fields are filled
    given(annex7(), fillState([answer(1, "ZH-2026-0412"), answer(2, "Canton of Zurich")]));

    // When it opens, the first empty field is selected in the list and on the document
    const item = await screen.findByRole("listitem", { name: "Name and legal form" });
    expect(item).toHaveAttribute("aria-current", "true");
    expect(zone(3)).toHaveAttribute("aria-pressed", "true");
  });

  it("moves through the fields with the keyboard: ↓ ↑ j k, Enter to type", async () => {
    // Given the form is open, the first field selected
    const { user } = given();
    const items = () => fieldList().getAllByRole("listitem");
    await screen.findByRole("textbox", { name: "Telephone" });

    // When I press ↓ ↓ k j j
    await user.keyboard("{ArrowDown}{ArrowDown}kjj");

    // Then the fourth field is selected
    expect(items()[3]).toHaveAttribute("aria-current", "true");

    // And ↑ then Enter puts me in the third field's input
    await user.keyboard("{ArrowUp}{Enter}");
    expect(screen.getByRole("textbox", { name: "Name and legal form" })).toHaveFocus();
  });

  it("tells me when a value could not be saved", async () => {
    // Given the back refuses the save
    given();
    server.use(handlers.error("/forms/2/fields/6", 500, "Boom", "patch"));
    const user = userEvent.setup();

    // When I type a value and leave the field
    await user.type(await screen.findByRole("textbox", { name: "Telephone" }), "044");
    await user.tab();

    // Then I am told it is not saved, and the form does not pretend it is
    expect(await screen.findByRole("status")).toHaveTextContent("Not saved");
    expect(screen.getByText("0 / 9 filled · 9 empty")).toBeInTheDocument();
  });

  it("leads to the export in the original format", async () => {
    // Given the form is open
    given();

    // Then the export action names the original format
    expect(await screen.findByRole("link", { name: "Export PDF" })).toHaveAttribute(
      "href",
      "/forms/2/export",
    );
  });

  it("tells me when a form cannot be filled yet (format not supported)", async () => {
    // Given the Word form, not parsed yet
    const docx = formSummary();
    given(annex7({ ...docx, id: 2, field_counts: null, pages: [], fields: [] }), fillState([], []));

    // Then I am told so
    expect(
      await screen.findByRole("heading", { name: "This form can't be filled yet" }),
    ).toBeInTheDocument();
  });

  it("tells me when the form does not exist", async () => {
    // Given an unknown form
    server.use(
      handlers.error("/forms/2", 404, "Form 2 not found"),
      handlers.error("/forms/2/answers", 404, "Form 2 not found"),
    );

    // When I open it
    renderScreen(<LiveFillScreen formId={2} />);

    // Then I am told so
    expect(await screen.findByRole("heading", { name: "Form not found" })).toBeInTheDocument();
  });

  it("lets me retry when the form could not be loaded", async () => {
    // Given the back fails once
    server.use(handlers.error("/forms/2", 500), handlers.answers(2, fillState()));
    const user = userEvent.setup();
    renderScreen(<LiveFillScreen formId={2} />);
    const alert = await screen.findByRole("alert");

    // When it is back and I retry
    server.use(handlers.form(annex7()), handlers.tender(tender()));
    await user.click(within(alert).getByRole("button", { name: "Try again" }));

    // Then the form shows
    expect(await screen.findByRole("textbox", { name: "Telephone" })).toBeInTheDocument();
  });
});

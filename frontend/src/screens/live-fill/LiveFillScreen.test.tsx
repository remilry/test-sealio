import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { renderDocument } from "docx-preview";
import { delay, http } from "msw";
import { API_URL } from "@/shared/api";
import { handlers, renderScreen, server } from "@/shared/test";
import {
  aiAnswer,
  candidate,
  citation,
  knowledgeBase,
  aiRun,
  annex4,
  annex4Field,
  annex4Fields,
  annex4File,
  annex7,
  annex7Fields,
  answer,
  exportSummary,
  fillState,
  form as formSummary,
  tender,
  type Answer,
  type FillState,
} from "@/shared/test/fixtures";
import { LiveFillScreen } from "./LiveFillScreen";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
// The real docx-preview, watched: a Word document must be rendered once, not at every keystroke.
vi.mock("docx-preview", async (original) => {
  const actual = await original<typeof import("docx-preview")>();
  return { ...actual, renderDocument: vi.fn(actual.renderDocument) };
});

beforeEach(() => {
  push.mockClear();
  server.use(handlers.knowledge(knowledgeBase()));
});

const fieldList = () => within(screen.getByRole("list", { name: "Fields" }));
const preview = () => screen.getByRole("region", { name: "Form preview" });
/** The zone drawn on the document for a field (the only place where data-field-id is used). */
const zone = (fieldId: number) =>
  preview().querySelector<HTMLButtonElement>(`[data-field-id="${fieldId}"]`)!;
/** The same zone, waited for: the document preview is loaded lazily. */
const findZone = (fieldId: number) =>
  waitFor(() => {
    const found = preview().querySelector<HTMLButtonElement>(`[data-field-id="${fieldId}"]`);
    if (!found) throw new Error(`No zone for field ${fieldId} on the document yet`);
    return found;
  });

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

    // Then the original PDF is rendered (loaded lazily, so waited for) with one zone per field,
    // placed from the parser's box
    await waitFor(() =>
      expect(preview().querySelector("[data-pdf-file]")).toHaveAttribute(
        "data-pdf-file",
        "http://localhost:8000/forms/2/file",
      ),
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
    expect(screen.getByText("2 / 9 filled · 7 empty · 0 doubts")).toBeInTheDocument();
    expect(fieldList().getByRole("textbox", { name: "Name and legal form" })).toHaveValue(
      "Alpenlogic AG",
    );
    expect(within(await findZone(3)).getByText("Alpenlogic AG")).toBeInTheDocument();
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
    expect(await within(await findZone(6)).findByText("+41 44 512 38 00")).toBeInTheDocument();
    expect(await screen.findByText("1 / 9 filled · 8 empty · 0 doubts")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Saved");
    const card = within(fieldList().getByRole("listitem", { name: "Telephone" }));
    expect(card.getByText("Entered by you · 14:45")).toBeInTheDocument();
  });

  it("shows what I type on the form at every keystroke, before it is saved", async () => {
    // Given an empty form
    const { saved, user } = given();
    const telephone = await screen.findByRole("textbox", { name: "Telephone" });

    // When I type the first characters
    await user.type(telephone, "+4");

    // Then the document shows them already, though nothing is saved yet
    expect(within(await findZone(6)).getByText("+4")).toBeInTheDocument();
    await user.type(telephone, "1");
    expect(within(zone(6)).getByText("+41")).toBeInTheDocument();
    expect(saved.requests).toEqual([]);

    // And erasing everything shows the field empty again
    await user.clear(telephone);
    expect(within(zone(6)).queryByText(/\+4/)).not.toBeInTheDocument();
  });

  it("shows the dot leaders of a field only while it is empty", async () => {
    // Given the project field, printed with dot leaders, and empty
    const { user } = given();
    const project = await screen.findByRole("textbox", {
      name: "Project number/project title/project name",
    });
    const masks = () => preview().querySelectorAll<HTMLElement>('[data-placeholder-of="1"]');
    expect(masks()).toHaveLength(0);

    // When I type in it, then its dots are covered, exactly where the parser found them
    await user.type(project, "ZH");
    expect(masks()).toHaveLength(1);
    expect(masks()[0].style.left).toBe(`${(270.2 / 595.3) * 100}%`);
    expect(masks()[0].style.width).toBe(`${((395.7 - 270.2) / 595.3) * 100}%`);

    // And when I erase it, the dots show again
    await user.clear(project);
    expect(masks()).toHaveLength(0);
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
    expect(await screen.findByText("0 / 9 filled · 9 empty · 0 doubts")).toBeInTheDocument();
  });

  it("clicking a field on the document puts me in its input", async () => {
    // Given the form is open
    const { user } = given();
    await screen.findByRole("textbox", { name: "E-mail" });

    // When I click the e-mail zone on the document
    await user.click(await findZone(7));

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
    expect(await findZone(3)).toHaveAttribute("aria-pressed", "true");
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

  it("keeps what I typed when it could not be saved, so I can try again", async () => {
    // Given the back refuses the save
    const { saved } = given();
    server.use(handlers.error("/forms/2/fields/6", 500, "Boom", "patch"));
    const user = userEvent.setup();

    // When I type a value and leave the field
    const telephone = await screen.findByRole("textbox", { name: "Telephone" });
    await user.type(telephone, "044");
    await user.tab();

    // Then I am told it is not saved, without technical details, and the form does not pretend it is
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Couldn't save — press Enter in the field to try again",
    );
    expect(screen.getByText("0 / 9 filled · 9 empty · 0 doubts")).toBeInTheDocument();
    // But what I typed is still there, on the form too
    const card = within(fieldList().getByRole("listitem", { name: "Telephone" }));
    expect(card.getByRole("textbox")).toHaveValue("044");
    expect(card.getByText("Not saved — press Enter to try again")).toBeInTheDocument();
    expect(within(await findZone(6)).getByText("044")).toBeInTheDocument();

    // And when the back is reachable again, Enter saves it
    server.use(saved.handler);
    await user.type(card.getByRole("textbox"), "{Enter}");
    await waitFor(() => expect(saved.requests).toEqual([{ fieldId: 6, value: "044" }]));
    expect(await screen.findByText("1 / 9 filled · 8 empty · 0 doubts")).toBeInTheDocument();
    expect(card.queryByText(/Not saved/)).not.toBeInTheDocument();
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
    // (told in plain words, nothing technical)
    expect(alert).toHaveTextContent(
      "We couldn't load this form.Something went wrong on our side. Please try again in a moment.",
    );

    // When it is back and I retry
    server.use(handlers.form(annex7()), handlers.tender(tender()));
    await user.click(within(alert).getByRole("button", { name: "Try again" }));

    // Then the form shows
    expect(await screen.findByRole("textbox", { name: "Telephone" })).toBeInTheDocument();
  });
});

/**
 * A back running the automatic fill of Annex 7: the answers follow the stream (as the back
 * persists each answer before publishing it), and the user's saves are kept too.
 */
function fillingBack() {
  let state = fillState([], annex7Fields, aiRun("running"));
  let nextId = 1;
  const stream = handlers.fillEvents(2);
  const withAnswer = (entry: Answer) => {
    const others = state.answers.filter((a) => a.field_id !== entry.field_id);
    state = fillState([...others, entry], annex7Fields, state.ai_run);
  };
  const saved = handlers.saveField(2, (fieldId, { value }) => {
    withAnswer(answer(fieldId, value?.trim() || null, "2026-11-04T10:00:12Z"));
    return state;
  });
  server.use(
    handlers.form(annex7()),
    handlers.tender(tender()),
    handlers.answers(2, () => state),
    saved.handler,
    stream.handler,
  );
  const send = (event: Record<string, unknown> & { type: string }) =>
    stream.send({ id: nextId++, ...event });
  return {
    saved,
    stream,
    phase: (phase: string, extra: Record<string, unknown> = {}) =>
      send({ type: "phase", phase, ...extra }),
    searching: (...fieldIds: number[]) =>
      fieldIds.forEach((fieldId) => send({ type: "field", field_id: fieldId, state: "searching" })),
    answered: (fieldId: number, value: string, type: Answer["type"] = "auto") => {
      const entry = aiAnswer(fieldId, value, type ?? "auto");
      // The back keeps the user's value: it only publishes the answer.
      if (state.answers.find((a) => a.field_id === fieldId)?.resolved_by !== "user") {
        withAnswer(entry);
      }
      send({
        type: "field",
        field_id: fieldId,
        state: "answered",
        answer: entry,
        counts: state.counts,
      });
    },
    done: (summary: { filled: number; fillable: number; doubts: number; seconds: number }) => {
      state = { ...state, ai_run: aiRun("done") };
      send({ type: "done", ...summary });
      stream.close();
    },
    error: (message: string) => {
      state = { ...state, ai_run: aiRun("failed") };
      send({ type: "error", message });
      stream.close();
    },
  };
}

function watchFill() {
  const back = fillingBack();
  const user = userEvent.setup();
  const view = renderScreen(<LiveFillScreen formId={2} />);
  return { back, user, view };
}

/** The phases before the search, as the back sends them for Annex 7 (9 fields to answer). */
function startSearch(back: ReturnType<typeof fillingBack>) {
  back.phase("reading_form");
  back.phase("detecting_fields", { to_answer: 9 });
  back.phase("searching");
}

describe("Live fill (watching the automatic fill)", () => {
  it("tells me the form is filling, how far it is, and that the export waits", async () => {
    // Given a fill that is reading the form
    const { back } = watchFill();
    back.phase("reading_form");

    // Then the left column says so, with a progress bar
    expect(await screen.findByRole("heading", { name: "Filling the form…" })).toBeInTheDocument();
    expect(await screen.findByText("Reading the form")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Fill progress" })).toBeInTheDocument();
    // And the export waits for the end of the fill
    expect(screen.getByRole("button", { name: "Filling…" })).toBeDisabled();

    // And the phase follows the run
    back.phase("detecting_fields", { to_answer: 9 });
    expect(await screen.findByText("Detecting fields")).toBeInTheDocument();
    back.phase("searching");
    expect(await screen.findByText("Searching your documents")).toBeInTheDocument();
    expect(screen.getByText("0 / 9")).toBeInTheDocument();
    back.stream.close();
  });

  it("shows each answer in the list and on the form as soon as it is found", async () => {
    // Given the fill searching three fields
    const { back } = watchFill();
    startSearch(back);
    back.searching(3, 4, 6);

    // Then they show as searched
    await screen.findByRole("list", { name: "Fields" });
    const card = (label: string) => within(fieldList().getByRole("listitem", { name: label }));
    expect(
      await card("Name and legal form").findByText("Searching your documents…"),
    ).toBeInTheDocument();
    expect(card("Telephone").getByText("Searching your documents…")).toBeInTheDocument();
    expect(card("E-mail").queryByText("Searching your documents…")).not.toBeInTheDocument();

    // When the name is found
    back.answered(3, "Alpenlogic AG");

    // Then it shows in its input and on the form, the others still searched
    await waitFor(() =>
      expect(card("Name and legal form").getByRole("textbox")).toHaveValue("Alpenlogic AG"),
    );
    expect(card("Name and legal form").queryByText("Searching your documents…")).toBeNull();
    expect(within(await findZone(3)).getByText("Alpenlogic AG")).toBeInTheDocument();
    const legend = within(within(preview()).getByRole("list", { name: "Legend" }));
    expect(legend.getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Filled automatically",
      "To check",
      "Empty",
      "Entered by you",
      "Sign by hand",
    ]);
    expect(card("Telephone").getByText("Searching your documents…")).toBeInTheDocument();
    expect(card("Business address").getByText("Searching your documents…")).toBeInTheDocument();
    expect(zone(3)).toHaveAttribute("data-tone", "auto");
    expect(zone(4)).toHaveAttribute("data-tone", "searching");
    // And the counters follow
    expect(screen.getByText("1 / 9 filled · 8 empty · 0 doubts")).toBeInTheDocument();
    expect(screen.getByText("1 / 9")).toBeInTheDocument();
    back.stream.close();
  });

  it("sums up the fill at the end, enables the export and selects the first open field", async () => {
    // Given a fill that found 8 of the 9 values (not the business address)
    const { back } = watchFill();
    startSearch(back);
    const values: [number, string][] = [
      [1, "ZH-2026-0412"],
      [2, "Canton of Zurich"],
      [3, "Alpenlogic AG"],
      [5, "Marc Keller"],
      [6, "+41 44 512 38 00"],
      [7, "info@alpenlogic.ch"],
      [8, "Zurich, 04.11.2026"],
      [9, "Marc Keller"],
    ];
    values.forEach(([fieldId, value]) => back.answered(fieldId, value));
    back.phase("cross_checking");
    back.phase("preparing_review");
    expect(await screen.findByText("Preparing your review")).toBeInTheDocument();

    // When it ends
    back.done({ filled: 8, fillable: 9, doubts: 0, seconds: 23 });

    // Then it is summed up, and the export is ready
    expect(await screen.findByText("8 of 9 fields filled in 23 seconds")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Export PDF" })).toBeEnabled();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "1 field to fill" })).toBeInTheDocument();
    // And the field left open is selected
    expect(fieldList().getByRole("listitem", { name: "Business address" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(screen.getByText("8 / 9 filled · 1 empty · 0 doubts")).toBeInTheDocument();
  });

  it("tells me when the fill stopped, and keeps the answers already found", async () => {
    // Given a fill that found the name
    const { back } = watchFill();
    startSearch(back);
    back.answered(3, "Alpenlogic AG");
    back.searching(4);
    expect(await screen.findByText("1 / 9")).toBeInTheDocument();
    const address = within(fieldList().getByRole("listitem", { name: "Business address" }));
    expect(await address.findByText("Searching your documents…")).toBeInTheDocument();

    // When it fails
    back.error("the documents could not be read");

    // Then I am told, the bar gives way to the message, and the name stays
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Auto-fill stopped: the documents could not be read",
    );
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(fieldList().getByRole("textbox", { name: "Name and legal form" })).toHaveValue(
      "Alpenlogic AG",
    );
    expect(await screen.findByRole("button", { name: "Export PDF" })).toBeEnabled();
    // And the field it was searching is no longer shown as searched
    expect(address.queryByText("Searching your documents…")).not.toBeInTheDocument();
    expect(address.getByText("Empty — exported blank")).toBeInTheDocument();
    expect((await findZone(4)).getAttribute("data-tone")).not.toBe("searching");
  });

  it("keeps what I am typing when the fill answers the same field, and saves it", async () => {
    // Given the fill searching the telephone, which I start typing
    const { back, user } = watchFill();
    startSearch(back);
    back.searching(6);
    const telephone = await screen.findByRole("textbox", { name: "Telephone" });
    await user.type(telephone, "044 000");

    // When the fill answers that field while I type
    back.answered(6, "+41 44 512 38 00");
    await waitFor(() =>
      expect(
        within(fieldList().getByRole("listitem", { name: "Telephone" })).queryByText(
          "Searching your documents…",
        ),
      ).toBeNull(),
    );

    // Then my text is still in the input
    expect(telephone).toHaveValue("044 000");
    await user.type(telephone, " 11");
    expect(telephone).toHaveValue("044 000 11");

    // And leaving the field saves what I typed
    await user.tab();
    await waitFor(() => expect(back.saved.requests).toEqual([{ fieldId: 6, value: "044 000 11" }]));
    expect(within(await findZone(6)).getByText("044 000 11")).toBeInTheDocument();
    back.stream.close();
  });

  it("shows a value I save while its field is searched as mine at once", async () => {
    // Given the fill searching the telephone
    const { back, user } = watchFill();
    startSearch(back);
    back.searching(6);
    const card = within(await screen.findByRole("listitem", { name: "Telephone" }));
    expect(await card.findByText("Searching your documents…")).toBeInTheDocument();

    // When I type a value and leave the field, before the fill answers it
    await user.type(card.getByRole("textbox"), "044 000 11");
    await user.tab();

    // Then it is shown as entered by me, in the list and on the form
    expect(await card.findByText(/Entered by you/)).toBeInTheDocument();
    expect(card.queryByText("Searching your documents…")).not.toBeInTheDocument();
    await waitFor(() => expect(zone(6)).toHaveAttribute("data-tone", "entered"));
    back.stream.close();
  });

  it("picks up where the fill was when I reload the page", async () => {
    // Given a fill that already found two values and is searching a third
    const { back, view } = watchFill();
    startSearch(back);
    back.answered(3, "Alpenlogic AG");
    back.answered(6, "+41 44 512 38 00");
    back.searching(7);
    expect(await screen.findByText("2 / 9")).toBeInTheDocument();

    // When I reload the page (the back replays the run, which goes on)
    view.unmount();
    renderScreen(<LiveFillScreen formId={2} />);

    // Then the same answers, phase and counts show, nothing counted twice
    expect(await screen.findByText("2 / 9")).toBeInTheDocument();
    expect(screen.getByText("Searching your documents")).toBeInTheDocument();
    expect(screen.getByText("2 / 9 filled · 7 empty · 0 doubts")).toBeInTheDocument();
    expect(fieldList().getByRole("textbox", { name: "Name and legal form" })).toHaveValue(
      "Alpenlogic AG",
    );
    expect(fieldList().getByRole("textbox", { name: "Telephone" })).toHaveValue("+41 44 512 38 00");
    expect(
      within(fieldList().getByRole("listitem", { name: "E-mail" })).getByText(
        "Searching your documents…",
      ),
    ).toBeInTheDocument();
    expect(back.stream.connections()).toBe(2);
    back.stream.close();
  });

  it("does not follow any fill when none is running", async () => {
    // Given a form with no fill running
    const stream = handlers.fillEvents(2);
    server.use(stream.handler);
    given();

    // When it opens, then the usual header shows and no stream is read
    expect(await screen.findByRole("heading", { name: "9 fields to fill" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Export PDF" })).toBeEnabled();
    expect(stream.connections()).toBe(0);
  });
});

const ALL_FILLED = [1, 2, 3, 4, 5, 6, 7, 8, 9];

/** Opens the export over the form, the back answering with the given summary. */
async function openExport(summary = exportSummary(ALL_FILLED), answers = fillState()) {
  server.use(handlers.exportSummary(2, summary));
  const { saved, user } = given(annex7(), answers);
  await user.click(await screen.findByRole("button", { name: "Export PDF" }));
  return { dialog: await screen.findByRole("dialog"), saved, user };
}

describe("Export (dialog over the form)", () => {
  it("says the form is ready when every field is filled", async () => {
    // Given every fillable field has a value, when I open the export
    const { dialog } = await openExport();

    // Then it is ready, with no warning
    const panel = within(dialog);
    expect(await panel.findByRole("heading", { name: "Ready to submit" })).toBeInTheDocument();
    expect(
      panel.getByText("Annex 7 — Sanctions self-declaration (Art. 29c) · 9 of 9 fields filled"),
    ).toBeInTheDocument();
    expect(panel.queryByRole("list", { name: "Empty fields" })).not.toBeInTheDocument();
  });

  it("warns that empty fields will be exported blank, and lets me go back to them", async () => {
    // Given two fields are filled, when I open the export
    const { dialog, user } = await openExport(exportSummary([3, 6]));

    // Then I see which fields will be blank, and can still download
    const panel = within(dialog);
    expect(await panel.findByRole("heading", { name: "7 fields still empty" })).toBeInTheDocument();
    expect(panel.getByText("7 fields still empty — they will be exported blank")).toBeVisible();
    const empty = within(panel.getByRole("list", { name: "Empty fields" }));
    expect(empty.getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Project number/project title/project name",
      "Name of the contracting authority",
      "Business address",
      "Contact person",
      "E-mail",
      "Place and date",
      "First name(s) and surname(s)",
    ]);
    expect(panel.getByRole("link", { name: "Download PDF" })).toBeInTheDocument();

    // And going back closes it, the form still there
    await user.click(panel.getByRole("button", { name: "Back to review" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("textbox", { name: "Telephone" })).toBeInTheDocument();
  });

  it("downloads the filled form in its original format, and reminds me to sign by hand", async () => {
    // Given the form, when I open the export
    const { dialog } = await openExport();

    // Then the download is the filled PDF from the back
    const panel = within(dialog);
    const download = await panel.findByRole("link", { name: "Download PDF" });
    expect(download).toHaveAttribute("href", "http://localhost:8000/forms/2/export/file");
    expect(
      panel.getByText(
        "Buyer's original layout preserved · answers written into the existing fields",
      ),
    ).toBeInTheDocument();
    // And the signature is listed before submitting
    const section = panel.getByRole("region", { name: "Before you submit" });
    expect(within(section).getByText("Sign by hand: Signature(s)")).toBeInTheDocument();
  });

  it("counts the value I was typing when I opened it", async () => {
    // Given the back's summary counts the values it has received
    const { user, saved } = given();
    server.use(
      handlers.exportSummary(2, () =>
        exportSummary(saved.requests.filter((r) => r.value).map((r) => r.fieldId)),
      ),
    );

    // When I type a value and open the export straight away
    await user.type(await screen.findByRole("textbox", { name: "Telephone" }), "044");
    await user.click(screen.getByRole("button", { name: "Export PDF" }));

    // Then the value is saved first, and the export counts it
    const panel = within(await screen.findByRole("dialog"));
    expect(await panel.findByText(/1 of 9 fields filled/)).toBeInTheDocument();
    expect(saved.requests).toEqual([{ fieldId: 6, value: "044" }]);
  });

  it("lets me retry when the export could not be prepared", async () => {
    // Given the back fails once
    server.use(handlers.error("/forms/2/export", 500));
    const { user } = given();
    await user.click(await screen.findByRole("button", { name: "Export PDF" }));
    const alert = await within(await screen.findByRole("dialog")).findByRole("alert");

    // When it is back and I retry
    server.use(handlers.exportSummary(2, exportSummary(ALL_FILLED)));
    await user.click(within(alert).getByRole("button", { name: "Try again" }));

    // Then the export shows
    expect(await screen.findByRole("heading", { name: "Ready to submit" })).toBeInTheDocument();
  });
});

describe("Live fill (status and source of each answer)", () => {
  const card = (label: string) => within(fieldList().getByRole("listitem", { name: label }));
  const findCard = async (label: string) => {
    await screen.findByRole("list", { name: "Fields" });
    return card(label);
  };

  it("shows where an automatic answer comes from: document, page and quote", async () => {
    // Given a name found in the commercial register, page 2
    const found = aiAnswer(3, "Alpenlogic AG", "auto", undefined, {
      candidates: [
        candidate("Alpenlogic AG", [
          citation({
            quote: "Alpenlogic AG, Zurich",
            document_name: "Commercial register extract",
            page: 1,
          }),
        ]),
      ],
    });
    const { user } = given(annex7(), fillState([found]));

    // When I open that field
    await user.click(await screen.findByRole("textbox", { name: "Name and legal form" }));

    // Then it says it was filled automatically, with its source
    expect(card("Name and legal form").getByText("Filled automatically")).toBeInTheDocument();
    expect(
      card("Name and legal form").getByText("Commercial register extract, page 2"),
    ).toBeInTheDocument();
    expect(card("Name and legal form").getByText(/“?Alpenlogic AG, Zurich”?/)).toBeInTheDocument();
  });

  it("reads the 0-based page of a citation as a 1-based page number", async () => {
    // Given an answer found on the first page of a document (page 0 in the API)
    const found = aiAnswer(3, "Alpenlogic AG", "auto", undefined, {
      candidates: [
        candidate("Alpenlogic AG", [
          citation({ document_name: "Commercial register extract", page: 0 }),
        ]),
      ],
    });
    const { user } = given(annex7(), fillState([found]));

    // When I open that field
    await user.click(await screen.findByRole("textbox", { name: "Name and legal form" }));

    // Then the source reads page 1
    expect(
      card("Name and legal form").getByText("Commercial register extract, page 1"),
    ).toBeInTheDocument();
  });

  it("shows the source of the selected field only, the others are collapsed", async () => {
    // Given two automatic answers with a source each
    const withSource = (id: number, value: string, document_name: string) =>
      aiAnswer(id, value, "auto", undefined, {
        candidates: [candidate(value, [citation({ document_name, quote: `q-${id}` })])],
      });
    const { user } = given(
      annex7(),
      fillState([
        withSource(3, "Alpenlogic AG", "Register A"),
        withSource(4, "Bahnhofstrasse 1", "Register B"),
      ]),
    );
    await screen.findByRole("textbox", { name: "Name and legal form" });

    // When I select the name
    await user.click(screen.getByRole("textbox", { name: "Name and legal form" }));

    // Then only its source shows
    expect(card("Name and legal form").getByText("Register A, page 1")).toBeInTheDocument();
    expect(card("Business address").queryByText("Register B, page 1")).not.toBeInTheDocument();
    expect(card("Business address").getByText("1 source")).toBeInTheDocument();
  });

  it("calls the tender documents by their name when the source is the tender", async () => {
    // Given an answer found in the tender details
    const found = aiAnswer(2, "Canton of Zurich", "auto", undefined, {
      candidates: [
        candidate("Canton of Zurich", [
          citation({ document_id: null, document_name: "Tender", page: null }),
        ]),
      ],
    });
    const { user } = given(annex7(), fillState([found]));

    // When I open that field
    await user.click(
      await screen.findByRole("textbox", { name: "Name of the contracting authority" }),
    );

    // Then the source is "Tender details"
    expect(
      card("Name of the contracting authority").getByText("Tender details"),
    ).toBeInTheDocument();
  });

  it("tells me I declare on behalf of the company for a declaration", async () => {
    // Given a ticked declaration
    const declared = aiAnswer(3, "Yes", "declaration", undefined, {
      candidates: [candidate("Yes")],
    });
    given(annex7(), fillState([declared]));

    // Then the status names the company
    expect(
      await (
        await findCard("Name and legal form")
      ).findByText("Filled automatically · you declare this on behalf of Alpenlogic AG"),
    ).toBeInTheDocument();
  });

  it("says nothing was found, and in how many documents it looked", async () => {
    // Given a field the search found nothing for, with 2 documents in the company knowledge
    given(annex7(), fillState([aiAnswer(4, null, "missing")]));

    // Then the status says so
    expect(
      await (
        await findCard("Business address")
      ).findByText("Not found in the passages searched in your 2 documents"),
    ).toBeInTheDocument();
  });

  it("says when only I can fill a field, why, and keeps the suggestion in the input", async () => {
    // Given a field only the user can fill, with a suggestion
    const manual = aiAnswer(5, "Marc Keller", "manual", undefined, {
      user_only_reason: "The contact person is chosen by the company.",
    });
    given(annex7(), fillState([manual]));

    // Then the status and the reason show, the suggestion is in the input
    const contact = await findCard("Contact person");
    expect(await contact.findByText("Only you can fill this")).toBeInTheDocument();
    expect(contact.getByText("The contact person is chosen by the company.")).toBeInTheDocument();
    expect(contact.getByRole("textbox")).toHaveValue("Marc Keller");
  });

  it.each([
    ["is slow", () => http.get(`${API_URL}/knowledge`, () => delay("infinite"))],
    ["fails", () => handlers.error("/knowledge", 500, "Something went wrong")],
  ])("never claims 0 documents while the company knowledge %s", async (_case, knowledgeHandler) => {
    // Given the company knowledge unknown, with a declaration and a missing answer
    server.use(knowledgeHandler());
    given(annex7(), fillState([aiAnswer(3, "Yes", "declaration"), aiAnswer(4, null, "missing")]));

    // Then the texts stay neutral
    expect(
      await (await findCard("Business address")).findByText("Not found in your documents"),
    ).toBeInTheDocument();
    expect(card("Name and legal form").getByText("Filled automatically")).toBeInTheDocument();
    expect(screen.queryByText(/0 documents/)).not.toBeInTheDocument();
    expect(screen.queryByText(/on behalf of/)).not.toBeInTheDocument();
  });

  it("lists every source when sources disagree", async () => {
    // Given two sources that disagree on the address
    const conflict = aiAnswer(4, "Bahnhofstrasse 1", "conflict", undefined, {
      candidates: [
        candidate("Bahnhofstrasse 1", [
          citation({ document_name: "Register extract", quote: "Bahnhofstrasse 1" }),
        ]),
        candidate("Seestrasse 9", [
          citation({ document_name: "Annual report", quote: "Seestrasse 9" }),
        ]),
      ],
    });
    const { user } = given(annex7(), fillState([conflict]));

    // When I open the field
    await user.click(await screen.findByRole("textbox", { name: "Business address" }));

    // Then the status counts the sources and all are shown; the selected value is in the input
    const address = card("Business address");
    expect(address.getByText("2 sources disagree")).toBeInTheDocument();
    expect(address.getByText("Register extract, page 1")).toBeInTheDocument();
    expect(address.getByText("Annual report, page 1")).toBeInTheDocument();
    expect(address.getByRole("textbox")).toHaveValue("Bahnhofstrasse 1");
  });

  it("shows the expiry date of an outdated source in Swiss format", async () => {
    // Given a value whose source expired
    const outdated = aiAnswer(6, "+41 44 512 38 00", "outdated", undefined, {
      candidates: [
        candidate("+41 44 512 38 00", [citation({ document_name: "Insurance certificate" })], {
          valid_until: { date: "2026-03-31", citation: citation() },
        }),
      ],
    });
    given(annex7(), fillState([outdated]));

    // Then the date is shown as dd.mm.yyyy
    expect(
      await (await findCard("Telephone")).findByText("Source expired on 31.03.2026"),
    ).toBeInTheDocument();
  });

  it("asks me to check a value only one of the two searches found", async () => {
    // Given a value only one run of the search found
    const unsure = aiAnswer(6, "+41 44 512 38 00", "unsure", undefined, {
      candidates: [candidate("+41 44 512 38 00", [citation({ document_name: "Brochure" })])],
    });
    given(annex7(), fillState([unsure]));

    // Then the card asks me to check it, and the document shows it as to check
    expect(
      await (await findCard("Telephone")).findByText("Found in one of two searches, check it"),
    ).toBeInTheDocument();
    expect(await findZone(6)).toHaveAttribute("data-tone", "toCheck");
  });

  it("asks me to check a value taken from an old document", async () => {
    // Given a value whose source is over a year old, with no validity date
    const old = aiAnswer(6, "+41 44 512 38 00", "outdated", undefined, {
      candidates: [
        candidate("+41 44 512 38 00", [citation({ document_name: "Annual report 2024" })], {
          source_date: { date: "2024-12-31", citation: citation() },
        }),
      ],
    });
    given(annex7(), fillState([old]));

    // Then the card gives the document's date and asks me to check it is still true
    expect(
      await (
        await findCard("Telephone")
      ).findByText("Source dated 31.12.2024, check it is still current"),
    ).toBeInTheDocument();
  });

  it("keeps the earlier source visible once I enter my own value", async () => {
    // Given a user value over a field that had an automatic source
    const mine = {
      ...answer(3, "Alpenlogic SA"),
      candidates: [candidate("Alpenlogic AG", [citation({ document_name: "Register A" })])],
    };
    const { user } = given(annex7(), fillState([mine]));

    // When I open it
    await user.click(await screen.findByRole("textbox", { name: "Name and legal form" }));

    // Then it says I entered it, and the source is still there
    expect(card("Name and legal form").getByText(/Entered by you/)).toBeInTheDocument();
    expect(card("Name and legal form").getByText("Register A, page 1")).toBeInTheDocument();
  });

  describe("discarding the answers", () => {
    async function openDiscard(user: ReturnType<typeof userEvent.setup>) {
      await user.click(await screen.findByRole("button", { name: "More actions" }));
      await user.click(await screen.findByRole("menuitem", { name: "Discard answers" }));
      return within(await screen.findByRole("alertdialog"));
    }

    it("discards after confirmation and takes me back to the tender", async () => {
      // Given a form with an answer
      const discard = handlers.discardFill(2);
      server.use(discard.handler);
      const { user } = given(annex7(), fillState([answer(3, "Alpenlogic AG")]));

      // When I discard from the top bar and confirm
      const dialog = await openDiscard(user);
      await user.click(dialog.getByRole("button", { name: "Discard" }));

      // Then the back deleted the answers and I am back on the tender
      await waitFor(() => expect(push).toHaveBeenCalledWith("/tenders/1"));
      expect(discard.state.discards).toBe(1);
    });

    it("works the same while the form is filling", async () => {
      // Given a fill running
      const discard = handlers.discardFill(2);
      server.use(discard.handler);
      const { back, user } = watchFill();
      back.phase("reading_form");
      expect(await screen.findByRole("heading", { name: "Filling the form…" })).toBeInTheDocument();

      // When I discard and confirm (the back ends the stream without a result, as it does when
      // the fill is discarded: the screen must not reconnect or fall into an error)
      const dialog = await openDiscard(user);
      back.stream.close();
      await user.click(dialog.getByRole("button", { name: "Discard" }));

      // Then I am back on the tender
      await waitFor(() => expect(push).toHaveBeenCalledWith("/tenders/1"));
      expect(discard.state.discards).toBe(1);
      // And the screen stopped following: no new stream, no error or "not found" meanwhile
      const connections = back.stream.connections();
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(back.stream.connections()).toBe(connections);
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(screen.queryByText("Form not found")).not.toBeInTheDocument();
      expect(screen.queryByText("We couldn't load this form.")).not.toBeInTheDocument();
    });
  });
});

describe("Live fill on a Word form", () => {
  const COMPANY = annex4Field("exact_company_name");
  const INSURER = annex4Field("insurance_company");

  function givenWord({
    file = annex4File(),
    answers = [],
    strict = false,
  }: { file?: Uint8Array | null; answers?: Answer[]; strict?: boolean } = {}) {
    let state = fillState(answers, annex4Fields);
    const saved = handlers.saveField(1, (fieldId, { value }) => {
      const others = state.answers.filter((a) => a.field_id !== fieldId);
      const entered = answer(fieldId, value?.trim() || null, "2026-11-05T09:00:00Z");
      state = fillState([...others, entered], annex4Fields);
      return state;
    });
    server.use(
      handlers.form(annex4()),
      handlers.tender(tender()),
      handlers.answers(1, () => state),
      handlers.formFile(1, file),
      saved.handler,
    );
    const user = userEvent.setup();
    const screenUi = <LiveFillScreen formId={1} />;
    const { rerender } = renderScreen(strict ? <StrictMode>{screenUi}</StrictMode> : screenUi);
    return { saved, user, rerender };
  }

  it("keeps the zones when I come back and a first rendering ends after the last one", async () => {
    // Given the Annex 4 seen once (its file is now cached)
    const { rerender } = givenWord({ strict: true });
    await findZone(COMPANY.id);
    // And, coming back, a first rendering slower than the next one (React runs effects twice in
    // development when a screen mounts with its data ready)
    const render = vi.mocked(renderDocument);
    const actual = render.getMockImplementation()!;
    let release = () => {};
    let late: Promise<unknown> = Promise.resolve();
    render.mockImplementationOnce((...args) => {
      late = new Promise<void>((resolve) => (release = resolve)).then(() => actual(...args));
      return late as ReturnType<typeof renderDocument>;
    });
    rerender(
      <StrictMode>
        <LiveFillScreen key="again" formId={1} />
      </StrictMode>,
    );
    await findZone(COMPANY.id);

    // When the first one ends at last
    release();
    await late;

    // Then the zones are still on the document
    await waitFor(() => expect(preview().querySelectorAll("[data-field-id]")).toHaveLength(49));
  });

  it("shows the Word form with each field highlighted where its answer goes", async () => {
    // Given the parsed Annex 4
    givenWord();

    // When the form opens, then the document is rendered with a zone per field
    const company = await findZone(COMPANY.id);
    expect(company).toHaveAccessibleName("Exact company name");
    expect(company).toHaveAttribute("data-tone", "empty");
    expect(preview().querySelectorAll("[data-field-id]")).toHaveLength(49);
  });

  it("shows what I type on the Word form at once, then saves it", async () => {
    // Given the Annex 4 open
    const { saved, user } = givenWord();
    await findZone(COMPANY.id);

    // When I type the company name
    await user.type(
      fieldList().getByRole("textbox", { name: "Exact company name" }),
      "Alpenlogic AG",
    );

    // Then it shows on the document before I leave the field
    expect(zone(COMPANY.id)).toHaveTextContent("Alpenlogic AG");
    // And leaving the field saves it, entered by me
    await user.tab();
    await waitFor(() =>
      expect(saved.requests).toEqual([{ fieldId: COMPANY.id, value: "Alpenlogic AG" }]),
    );
    await waitFor(() => expect(zone(COMPANY.id)).toHaveAttribute("data-tone", "entered"));
  });

  it("keeps the same document while I type, instead of rendering it again", async () => {
    // Given the Annex 4 open
    const { user } = givenWord();
    await findZone(COMPANY.id);
    vi.mocked(renderDocument).mockClear();

    // When I type a few characters and leave the field
    await user.type(fieldList().getByRole("textbox", { name: "Exact company name" }), "Alpen");
    await user.tab();
    await waitFor(() => expect(zone(COMPANY.id)).toHaveAttribute("data-tone", "entered"));

    // Then the document was not rendered again, and still shows the value
    expect(renderDocument).not.toHaveBeenCalled();
    expect(zone(COMPANY.id)).toHaveTextContent("Alpen");
  });

  it("selects a field when I click its zone on the Word form", async () => {
    // Given the Annex 4 open
    const { user } = givenWord();

    // When I click the insurance company's zone
    await user.click(await findZone(INSURER.id));

    // Then its input has the focus
    expect(fieldList().getByRole("textbox", { name: "Insurance company" })).toHaveFocus();
  });

  it("still lets me fill the fields when the Word document cannot be displayed", async () => {
    // Given a file the preview cannot load
    givenWord({ file: null });

    // Then I am told, and the fields are still there
    expect(await screen.findByText(/couldn't display this document/)).toBeInTheDocument();
    expect(fieldList().getByRole("textbox", { name: "Exact company name" })).toBeInTheDocument();
  });

  it("exports the Word form in its original format", async () => {
    // Given the Annex 4 open
    const { user } = givenWord();
    server.use(handlers.exportSummary(1, exportSummary([], { file_format: "docx" })));

    // When I open the export
    await user.click(await screen.findByRole("button", { name: "Export DOCX" }));

    // Then I download a DOCX
    const link = await screen.findByRole("link", { name: "Download DOCX" });
    expect(link).toHaveAttribute("href", "http://localhost:8000/forms/1/export/file");
  });

  const VAT = annex4Field("have_you_paid_in_full_the_vat_or_sales_tax_due");

  it("lets me answer a declaration with Yes or No, and clear it", async () => {
    // Given the Annex 4 open
    const { saved, user } = givenWord();
    await findZone(VAT.id);
    const card = within(fieldList().getByRole("listitem", { name: VAT.label }));

    // When I answer Yes
    await user.click(card.getByRole("radio", { name: "Yes" }));

    // Then it is saved and shows on the document, written in full
    await waitFor(() => expect(saved.requests).toEqual([{ fieldId: VAT.id, value: "yes" }]));
    await waitFor(() => expect(zone(VAT.id)).toHaveTextContent("Yes"));
    expect(card.getByRole("radio", { name: "Yes" })).toBeChecked();

    // And clearing it leaves the declaration unanswered
    await user.click(card.getByRole("button", { name: "Clear" }));
    await waitFor(() => expect(saved.requests.at(-1)).toEqual({ fieldId: VAT.id, value: null }));
    await waitFor(() => expect(card.getByRole("radio", { name: "Yes" })).not.toBeChecked());
  });

  it("shows a declaration answered Yes, however it was written", async () => {
    // Given a declaration already answered "Yes"
    givenWord({ answers: [answer(VAT.id, "Yes")] });

    // Then Yes is selected
    const card = within(await screen.findByRole("listitem", { name: VAT.label }));
    expect(card.getByRole("radio", { name: "Yes" })).toBeChecked();
    expect(card.getByRole("radio", { name: "No" })).not.toBeChecked();
  });
});

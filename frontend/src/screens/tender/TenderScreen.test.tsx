import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { API_URL } from "@/shared/api";
import { freezeToday, handlers, renderScreen, server } from "@/shared/test";
import { form, knowledgeBase, knowledgeDocument, tender } from "@/shared/test/fixtures";
import { TenderScreen } from "./TenderScreen";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const forms = () => within(screen.getByRole("list", { name: "Forms to complete" }));

describe("Tender", () => {
  beforeEach(() => {
    push.mockClear();
    freezeToday("2026-11-03");
    server.use(handlers.knowledge(knowledgeBase()));
  });

  it("shows what the tender is, who runs it and when it is due", async () => {
    // Given the seeded tender
    server.use(handlers.tender(tender()));

    // When I open it
    renderScreen(<TenderScreen tenderId={1} />);

    // Then I see its identity and the time left
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Cloud Platform Services – Canton of Zurich",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Open procedure")).toBeInTheDocument();
    expect(screen.getByText("Ref. ZH-2026-0412")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Canton of Zurich, Office for Information Technology · 4-year framework contract · Lots 1 and 2",
      ),
    ).toBeInTheDocument();
    const due = screen.getByRole("group", { name: "Submission due" });
    expect(within(due).getByText("19.11.2026 · 16 days")).toBeInTheDocument();
  });

  it("lists the forms to complete in order, with their original format", async () => {
    // Given a tender with the two annexes
    server.use(handlers.tender(tender()));

    // When I open it
    renderScreen(<TenderScreen tenderId={1} />);

    // Then each form is a card with its format and status
    const items = await screen.findAllByRole("listitem");
    expect(items.map((item) => item.getAttribute("aria-label"))).toEqual([
      "Annex 4 — Conditions of participation and self-declaration",
      "Annex 7 — Sanctions self-declaration (Art. 29c)",
    ]);
    const annex4 = within(forms().getByRole("listitem", { name: /Annex 4/ }));
    expect(annex4.getByText("DOCX")).toBeInTheDocument();
    expect(annex4.getByText("Not started")).toBeInTheDocument();
    const annex7 = within(forms().getByRole("listitem", { name: /Annex 7/ }));
    expect(annex7.getByText("PDF")).toBeInTheDocument();
  });

  it("shows what was detected in each form", async () => {
    // Given the seeded tender: Annex 7 parsed, Annex 4 (Word) not parsed yet
    server.use(handlers.tender(tender()));

    // When I open it
    renderScreen(<TenderScreen tenderId={1} />);

    // Then the parsed form shows its counts, the other its file name
    const annex7 = within(await screen.findByRole("listitem", { name: /Annex 7/ }));
    expect(annex7.getByText("10 fields detected · 1 signature")).toBeInTheDocument();
    const annex4 = within(forms().getByRole("listitem", { name: /Annex 4/ }));
    expect(
      annex4.getByText("Annex_4_Conditions of Participation and Company Self-Declaration.docx"),
    ).toBeInTheDocument();
  });

  it("cannot auto-fill a form whose format is not supported yet", async () => {
    // Given the Word form, not parsed yet
    server.use(handlers.tender(tender()));

    // When I open the tender
    renderScreen(<TenderScreen tenderId={1} />);

    // Then its auto-fill action is disabled
    const annex4 = within(await screen.findByRole("listitem", { name: /Annex 4/ }));
    expect(annex4.getByRole("button", { name: "Auto-fill" })).toBeDisabled();
  });

  describe("auto-fill", () => {
    const elevenDocuments = () =>
      knowledgeBase({
        documents: Array.from({ length: 11 }, (_, i) =>
          knowledgeDocument({ id: i + 1, file_name: `doc_${i + 1}.pdf` }),
        ),
      });

    async function openSetup(user: ReturnType<typeof userEvent.setup>) {
      const annex7 = within(await screen.findByRole("listitem", { name: /Annex 7/ }));
      await user.click(annex7.getByRole("button", { name: "Auto-fill" }));
      return within(await screen.findByRole("dialog"));
    }

    it("shows what the fill uses before starting", async () => {
      // Given a parsed form not started and eleven company documents
      server.use(handlers.tender(tender()), handlers.knowledge(elevenDocuments()));
      const user = userEvent.setup();
      renderScreen(<TenderScreen tenderId={1} />);

      // When I open Auto-fill
      const dialog = await openSetup(user);

      // Then I see the file, the sources and the duration
      expect(
        dialog.getByRole("heading", {
          name: "Auto-fill Annex 7 — Sanctions self-declaration (Art. 29c)",
        }),
      ).toBeInTheDocument();
      expect(
        dialog.getByText("Annex_7_Self-Declaration_Art29c_Ukraine_Ordinance.pdf"),
      ).toBeInTheDocument();
      expect(dialog.getByText("Company knowledge · 11 documents")).toBeInTheDocument();
      expect(dialog.getByText("Tender details")).toBeInTheDocument();
      expect(dialog.getByText("Takes about 25 seconds")).toBeInTheDocument();
    });

    it("starts the fill and opens the live fill", async () => {
      // Given the Setup dialog
      const fill = handlers.startFill(2);
      server.use(handlers.tender(tender()), handlers.knowledge(elevenDocuments()), fill.handler);
      const user = userEvent.setup();
      renderScreen(<TenderScreen tenderId={1} />);
      const dialog = await openSetup(user);

      // When I start
      await user.click(dialog.getByRole("button", { name: "Start" }));

      // Then the fill is requested and I land on the form
      await waitFor(() => expect(push).toHaveBeenCalledWith("/forms/2/fill"));
      expect(fill.state.starts).toBe(1);
    });

    it("sends nothing when I cancel", async () => {
      // Given the Setup dialog
      const fill = handlers.startFill(2);
      server.use(handlers.tender(tender()), handlers.knowledge(elevenDocuments()), fill.handler);
      const user = userEvent.setup();
      renderScreen(<TenderScreen tenderId={1} />);
      const dialog = await openSetup(user);

      // When I cancel
      await user.click(dialog.getByRole("button", { name: "Cancel" }));

      // Then it closes and nothing was sent
      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
      expect(fill.state.starts).toBe(0);
      expect(push).not.toHaveBeenCalled();
    });

    it("tells me when auto-fill is not available, and stays open", async () => {
      // Given the back cannot fill right now
      server.use(
        handlers.tender(tender()),
        handlers.knowledge(elevenDocuments()),
        handlers.error("/forms/2/fill", 503, "No API key configured", "post"),
      );
      const user = userEvent.setup();
      renderScreen(<TenderScreen tenderId={1} />);
      const dialog = await openSetup(user);

      // When I start
      await user.click(dialog.getByRole("button", { name: "Start" }));

      // Then the reason shows in the dialog
      expect(await dialog.findByText("Auto-fill is not available right now.")).toBeInTheDocument();
      expect(dialog.getByText("No API key configured")).toBeInTheDocument();
      expect(push).not.toHaveBeenCalled();
    });

    it("opens the live fill anyway when the form was already filled", async () => {
      // Given the back says it is already filled
      server.use(
        handlers.tender(tender()),
        handlers.knowledge(elevenDocuments()),
        handlers.error(
          "/forms/2/fill",
          409,
          "This form has already been filled. Discard its answers to auto-fill it again.",
          "post",
        ),
      );
      const user = userEvent.setup();
      renderScreen(<TenderScreen tenderId={1} />);
      const dialog = await openSetup(user);

      // When I start
      await user.click(dialog.getByRole("button", { name: "Start" }));

      // Then I go to the form
      await waitFor(() => expect(push).toHaveBeenCalledWith("/forms/2/fill"));
    });

    it("warns when the company knowledge is empty", async () => {
      // Given no company documents
      server.use(handlers.tender(tender()), handlers.knowledge(knowledgeBase({ documents: [] })));
      const user = userEvent.setup();
      renderScreen(<TenderScreen tenderId={1} />);

      // When I open Auto-fill
      const dialog = await openSetup(user);

      // Then I am warned and can add documents
      expect(
        dialog.getByText("Your company knowledge is empty: only the tender details can be used."),
      ).toBeInTheDocument();
      expect(dialog.getByRole("link", { name: "Add documents" })).toHaveAttribute(
        "href",
        "/knowledge",
      );
    });

    it("never says AI", async () => {
      // Given the tender with its Setup dialog open
      server.use(handlers.tender(tender()));
      const user = userEvent.setup();
      renderScreen(<TenderScreen tenderId={1} />);
      await openSetup(user);

      // Then no text on the screen mentions AI
      expect(screen.queryByText(/\bAI\b/)).not.toBeInTheDocument();
    });
  });

  describe("started forms", () => {
    const startedTender = (overrides: Partial<ReturnType<typeof form>> = {}) =>
      tender({
        forms: [
          form({
            id: 2,
            title: "Annex 7 — Sanctions self-declaration (Art. 29c)",
            file_format: "pdf",
            status: "in_review",
            field_counts: { fields: 10, yes_no: 0, signatures: 1 },
            ...overrides,
          }),
        ],
      });

    async function openDiscard(user: ReturnType<typeof userEvent.setup>) {
      const annex7 = within(await screen.findByRole("listitem", { name: /Annex 7/ }));
      expect(annex7.queryByRole("button", { name: "Auto-fill" })).not.toBeInTheDocument();
      await user.click(annex7.getByRole("button", { name: "More actions" }));
      await user.click(await screen.findByRole("menuitem", { name: "Discard answers" }));
      return within(await screen.findByRole("alertdialog"));
    }

    it("offers to continue, not to auto-fill again", async () => {
      // Given a form in review
      server.use(handlers.tender(startedTender()));
      renderScreen(<TenderScreen tenderId={1} />);

      // Then I can continue
      const annex7 = within(await screen.findByRole("listitem", { name: /Annex 7/ }));
      expect(annex7.getByRole("link", { name: "Continue review" })).toHaveAttribute(
        "href",
        "/forms/2/fill",
      );
      expect(annex7.queryByRole("button", { name: "Auto-fill" })).not.toBeInTheDocument();
    });

    it("only offers to continue while a fill is running", async () => {
      // Given a fill in progress
      server.use(handlers.tender(startedTender({ filling: true })));
      renderScreen(<TenderScreen tenderId={1} />);

      // Then only "Continue review" (and the menu) is there
      const annex7 = within(await screen.findByRole("listitem", { name: /Annex 7/ }));
      expect(annex7.getByRole("link", { name: "Continue review" })).toBeInTheDocument();
      expect(annex7.queryByRole("button", { name: "Auto-fill" })).not.toBeInTheDocument();
      expect(annex7.getByRole("button", { name: "More actions" })).toBeInTheDocument();
    });

    it("discards the answers after confirmation, and the form is not started again", async () => {
      // Given a form in review; the tender refreshes to "not started" once discarded
      const discard = handlers.discardFill(2);
      server.use(
        http.get(`${API_URL}/tenders/1`, () =>
          HttpResponse.json(
            discard.state.discards > 0 ? startedTender({ status: "not_started" }) : startedTender(),
          ),
        ),
        discard.handler,
      );
      const user = userEvent.setup();
      renderScreen(<TenderScreen tenderId={1} />);
      const dialog = await openDiscard(user);
      expect(
        dialog.getByText("Discard all answers to Annex 7 — Sanctions self-declaration (Art. 29c)?"),
      ).toBeInTheDocument();
      expect(
        dialog.getByText(
          "Every value is deleted, including the ones you entered. This can't be undone.",
        ),
      ).toBeInTheDocument();

      // When I confirm
      await user.click(dialog.getByRole("button", { name: "Discard" }));

      // Then the card is back to "Not started" with "Auto-fill"
      const annex7 = within(await screen.findByRole("listitem", { name: /Annex 7/ }));
      expect(await annex7.findByRole("button", { name: "Auto-fill" })).toBeInTheDocument();
      expect(annex7.getByText("Not started")).toBeInTheDocument();
      expect(discard.state.discards).toBe(1);
    });

    it("sends nothing when I cancel", async () => {
      // Given the confirmation
      const discard = handlers.discardFill(2);
      server.use(handlers.tender(startedTender()), discard.handler);
      const user = userEvent.setup();
      renderScreen(<TenderScreen tenderId={1} />);
      const dialog = await openDiscard(user);

      // When I cancel
      await user.click(dialog.getByRole("button", { name: "Cancel" }));

      // Then nothing was deleted
      await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
      expect(discard.state.discards).toBe(0);
    });

    it("tells me when the answers could not be discarded", async () => {
      // Given a back that fails
      server.use(
        handlers.tender(startedTender()),
        handlers.error("/forms/2/fill", 500, "boom", "delete"),
      );
      const user = userEvent.setup();
      renderScreen(<TenderScreen tenderId={1} />);
      const dialog = await openDiscard(user);

      // When I confirm
      await user.click(dialog.getByRole("button", { name: "Discard" }));

      // Then the failure is shown and the dialog stays
      expect(
        await dialog.findByText("We couldn't discard the answers. Try again."),
      ).toBeInTheDocument();
    });
  });

  it("lets me continue a form in review", async () => {
    // Given Annex 7 in review
    server.use(
      handlers.tender(
        tender({
          forms: [
            form({
              id: 2,
              title: "Annex 7 — Sanctions self-declaration (Art. 29c)",
              file_format: "pdf",
              status: "in_review",
              field_counts: { fields: 10, yes_no: 0, signatures: 1 },
            }),
          ],
        }),
      ),
    );

    // When I open the tender
    renderScreen(<TenderScreen tenderId={1} />);

    // Then I can continue where I left off
    const annex7 = within(await screen.findByRole("listitem", { name: /Annex 7/ }));
    expect(annex7.getByRole("link", { name: "Continue review" })).toHaveAttribute(
      "href",
      "/forms/2/fill",
    );
  });

  it("shows where each form stands: in review or ready", async () => {
    // Given one form in review and one ready
    server.use(
      handlers.tender(
        tender({
          forms: [
            form({ id: 1, status: "in_review" }),
            form({
              id: 2,
              title: "Annex 7 — Sanctions self-declaration (Art. 29c)",
              file_format: "pdf",
              status: "ready",
            }),
          ],
        }),
      ),
    );

    // When I open the tender
    renderScreen(<TenderScreen tenderId={1} />);

    // Then their statuses are shown
    const annex4 = within(await screen.findByRole("listitem", { name: /Annex 4/ }));
    expect(annex4.getByText("In review")).toBeInTheDocument();
    const annex7 = within(screen.getByRole("listitem", { name: /Annex 7/ }));
    expect(annex7.getByText("Ready")).toBeInTheDocument();
  });

  it.each([
    ["2026-11-18", "19.11.2026 · 1 day"],
    ["2026-11-19", "19.11.2026 · due today"],
    ["2026-11-20", "19.11.2026 · closed"],
  ])("on %s, the deadline reads “%s”", async (today, expected) => {
    // Given today's date
    freezeToday(today);
    server.use(handlers.tender(tender()));

    // When I open the tender
    renderScreen(<TenderScreen tenderId={1} />);

    // Then the deadline wording follows
    const due = await screen.findByRole("group", { name: "Submission due" });
    expect(within(due).getByText(expected)).toBeInTheDocument();
  });

  it("shows what the answers come from, with a way to manage it", async () => {
    // Given the seeded tender and knowledge base
    server.use(handlers.tender(tender()));

    // When I open the tender
    renderScreen(<TenderScreen tenderId={1} />);

    // Then the Company knowledge card counts the documents and links to them
    const card = within(await screen.findByRole("region", { name: "Company knowledge" }));
    expect(await card.findByText("2")).toBeInTheDocument();
    expect(card.getByText("documents")).toBeInTheDocument();
    expect(card.getByRole("link", { name: "Manage" })).toHaveAttribute("href", "/knowledge");
  });

  it("tells me when the tender does not exist", async () => {
    // Given an unknown tender
    server.use(handlers.error("/tenders/42", 404, "Tender 42 not found"));

    // When I open it
    renderScreen(<TenderScreen tenderId={42} />);

    // Then I am told so
    expect(await screen.findByRole("heading", { name: "Tender not found" })).toBeInTheDocument();
  });

  it("lets me retry when the tender could not be loaded", async () => {
    // Given the back fails once
    server.use(handlers.error("/tenders/1", 500));
    const user = userEvent.setup();
    renderScreen(<TenderScreen tenderId={1} />);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("We couldn't load this tender.")).toBeInTheDocument();

    // When the back is back and I retry
    server.use(handlers.tender(tender()));
    await user.click(within(alert).getByRole("button", { name: "Try again" }));

    // Then the tender shows
    expect(
      await screen.findByRole("heading", { level: 1, name: /Cloud Platform Services/ }),
    ).toBeInTheDocument();
  });
});

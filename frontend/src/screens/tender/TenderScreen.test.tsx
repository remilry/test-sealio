import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { freezeToday, handlers, renderScreen, server } from "@/shared/test";
import { form, tender } from "@/shared/test/fixtures";
import { TenderScreen } from "./TenderScreen";

const forms = () => within(screen.getByRole("list", { name: "Forms to complete" }));

describe("Tender", () => {
  beforeEach(() => freezeToday("2026-11-03"));

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
    expect(within(due).getByText("19 Nov 2026 · 16 days")).toBeInTheDocument();
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

  it("offers to fill a form that has not been started", async () => {
    // Given a form not started yet
    server.use(handlers.tender(tender({ forms: [form({ status: "not_started" })] })));

    // When I open the tender
    renderScreen(<TenderScreen tenderId={1} />);

    // Then I can see the AI fill action (wired to the Setup step later)
    const card = within(await screen.findByRole("listitem", { name: /Annex 4/ }));
    expect(card.getByRole("button", { name: "Fill with AI" })).toBeInTheDocument();
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
    ["2026-11-18", "19 Nov 2026 · 1 day"],
    ["2026-11-19", "19 Nov 2026 · due today"],
    ["2026-11-20", "19 Nov 2026 · closed"],
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

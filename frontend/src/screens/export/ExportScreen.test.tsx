import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { handlers, renderScreen, server } from "@/shared/test";
import { annex7, exportSummary } from "@/shared/test/fixtures";
import { ExportScreen } from "./ExportScreen";

const ALL_FILLED = [1, 2, 3, 4, 5, 6, 7, 8, 9];

describe("Export", () => {
  it("says the form is ready when every field is filled", async () => {
    // Given every fillable field has a value
    server.use(handlers.form(annex7()), handlers.exportSummary(2, exportSummary(ALL_FILLED)));

    // When I open the export
    renderScreen(<ExportScreen formId={2} />);

    // Then it is ready, with no warning
    expect(
      await screen.findByRole("heading", { level: 1, name: "Ready to submit" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Annex 7 — Sanctions self-declaration (Art. 29c)")).toBeInTheDocument();
    expect(screen.getByText("9 of 9 fields filled")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Empty fields" })).not.toBeInTheDocument();
  });

  it("warns that empty fields will be exported blank, and lets me go back", async () => {
    // Given two fields are filled
    server.use(handlers.form(annex7()), handlers.exportSummary(2, exportSummary([3, 6])));

    // When I open the export
    renderScreen(<ExportScreen formId={2} />);

    // Then I see which fields will be blank, and can still download
    expect(
      await screen.findByRole("heading", { level: 1, name: "7 fields still empty" }),
    ).toBeInTheDocument();
    expect(screen.getByText("7 fields still empty — they will be exported blank")).toBeVisible();
    const empty = within(screen.getByRole("list", { name: "Empty fields" }));
    expect(empty.getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Project number/project title/project name",
      "Name of the contracting authority",
      "Business address",
      "Contact person",
      "E-mail",
      "Place and date",
      "First name(s) and surname(s)",
    ]);
    expect(screen.getByRole("link", { name: "Back to review" })).toHaveAttribute(
      "href",
      "/forms/2/fill",
    );
    expect(screen.getByRole("link", { name: "Download PDF" })).toBeInTheDocument();
  });

  it("downloads the filled form in its original format", async () => {
    // Given the form
    server.use(handlers.form(annex7()), handlers.exportSummary(2, exportSummary(ALL_FILLED)));

    // When I open the export
    renderScreen(<ExportScreen formId={2} />);

    // Then the download is the filled PDF from the back
    const download = await screen.findByRole("link", { name: "Download PDF" });
    expect(download).toHaveAttribute("href", "http://localhost:8000/forms/2/export/file");
    expect(
      screen.getByText(
        "Buyer's original layout preserved · answers written into the existing fields",
      ),
    ).toBeInTheDocument();
  });

  it("reminds me to sign by hand", async () => {
    // Given a form with a signature
    server.use(handlers.form(annex7()), handlers.exportSummary(2, exportSummary(ALL_FILLED)));

    // When I open the export
    renderScreen(<ExportScreen formId={2} />);

    // Then the signature is listed before submitting
    const section = await screen.findByRole("region", { name: "Before you submit" });
    expect(within(section).getByText("Sign by hand: Signature(s)")).toBeInTheDocument();
  });

  it("tells me when the form does not exist", async () => {
    // Given an unknown form
    server.use(
      handlers.error("/forms/2", 404, "Form 2 not found"),
      handlers.error("/forms/2/export", 404, "Form 2 not found"),
    );

    // When I open its export
    renderScreen(<ExportScreen formId={2} />);

    // Then I am told so
    expect(await screen.findByRole("heading", { name: "Form not found" })).toBeInTheDocument();
  });

  it("lets me retry when the export could not be prepared", async () => {
    // Given the back fails once
    server.use(handlers.form(annex7()), handlers.error("/forms/2/export", 500));
    const user = userEvent.setup();
    renderScreen(<ExportScreen formId={2} />);
    const alert = await screen.findByRole("alert");

    // When it is back and I retry
    server.use(handlers.exportSummary(2, exportSummary(ALL_FILLED)));
    await user.click(within(alert).getByRole("button", { name: "Try again" }));

    // Then the export shows
    expect(await screen.findByRole("heading", { name: "Ready to submit" })).toBeInTheDocument();
  });
});

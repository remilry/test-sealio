import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { handlers, renderScreen, server } from "@/shared/test";
import { knowledgeBase, knowledgeDocument } from "@/shared/test/fixtures";
import { KnowledgeScreen } from "./KnowledgeScreen";

const documents = () => within(screen.getByRole("table", { name: "Documents" }));

describe("Company knowledge", () => {
  it("shows whose knowledge it is, how many documents and when it was last indexed", async () => {
    // Given the seeded knowledge base
    server.use(handlers.knowledge(knowledgeBase()));

    // When I open Company knowledge
    renderScreen(<KnowledgeScreen />);

    // Then I see the company and a summary (Zurich time)
    expect(
      await screen.findByRole("heading", { level: 1, name: "Alpenlogic AG" }),
    ).toBeInTheDocument();
    expect(screen.getByText("2 documents · last indexed 04.11.2026 at 13:29")).toBeInTheDocument();
  });

  it("lists each document with its format, pages, date added and status", async () => {
    // Given a PDF and a Word document, both indexed
    server.use(handlers.knowledge(knowledgeBase()));

    // When I open Company knowledge
    renderScreen(<KnowledgeScreen />);

    // Then each one is a row of the table
    const register = within(
      await screen.findByRole("row", { name: "Commercial register extract" }),
    );
    expect(register.getByText("PDF")).toBeInTheDocument();
    expect(register.getByText("01_commercial_register_extract.pdf")).toBeInTheDocument();
    expect(register.getByText("2 pages")).toBeInTheDocument();
    expect(register.getByText("04.11.2026")).toBeInTheDocument();
    expect(register.getByText("Indexed")).toBeInTheDocument();
    // A Word document has no fixed pages.
    const report = within(documents().getByRole("row", { name: "Annual report 2024" }));
    expect(report.getByText("DOCX")).toBeInTheDocument();
    expect(report.getByText("—")).toBeInTheDocument();
  });

  it("previews a PDF document in place when I click its name", async () => {
    // Given the seeded knowledge base
    server.use(handlers.knowledge(knowledgeBase()));
    const user = userEvent.setup();
    renderScreen(<KnowledgeScreen />);

    // When I click a PDF document's name
    await user.click(
      await screen.findByRole("button", { name: "Preview Commercial register extract" }),
    );

    // Then its pages show in a dialog, with a way to download it
    const dialog = await screen.findByRole("dialog", { name: "Commercial register extract" });
    const preview = within(dialog).getByRole("region", {
      name: "Preview of Commercial register extract",
    });
    expect(await within(preview).findByLabelText("Page 1")).toBeInTheDocument();
    expect(within(preview).getByLabelText("Page 2")).toBeInTheDocument();
    expect(within(dialog).getByText("01_commercial_register_extract.pdf")).toBeInTheDocument();
    expect(within(dialog).getByRole("link", { name: "Download" })).toHaveAttribute(
      "href",
      "http://localhost:8000/knowledge/documents/1/file",
    );

    // And closing it brings me back to the list
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("tells me a Word document cannot be previewed yet and lets me download it", async () => {
    // Given a Word document
    server.use(handlers.knowledge(knowledgeBase()));
    const user = userEvent.setup();
    renderScreen(<KnowledgeScreen />);

    // When I click its name
    await user.click(await screen.findByRole("button", { name: "Preview Annual report 2024" }));

    // Then I am told why there is no preview, and can download it
    const dialog = await screen.findByRole("dialog", { name: "Annual report 2024" });
    expect(
      within(dialog).getByRole("heading", { name: "No preview for Word documents yet" }),
    ).toBeInTheDocument();
    expect(within(dialog).getByRole("link", { name: "Download" })).toHaveAttribute(
      "href",
      "http://localhost:8000/knowledge/documents/9/file",
    );
  });

  it("lets me download any document straight from the list", async () => {
    // Given the seeded knowledge base
    server.use(handlers.knowledge(knowledgeBase()));

    // When I open Company knowledge
    renderScreen(<KnowledgeScreen />);

    // Then each row has its download link
    const register = within(
      await screen.findByRole("row", { name: "Commercial register extract" }),
    );
    const download = register.getByRole("link", { name: "Download Commercial register extract" });
    expect(download).toHaveAttribute("href", "http://localhost:8000/knowledge/documents/1/file");
    expect(download).toHaveAttribute("download");
  });

  it("tells me which document could not be read, and why", async () => {
    // Given a document the back could not read
    server.use(
      handlers.knowledge(
        knowledgeBase({
          documents: [
            knowledgeDocument({
              id: 12,
              name: "Scan of the insurance policy",
              file_name: "scan_of_the_insurance_policy.pdf",
              pages: null,
              status: "error",
              error: "No text found in this PDF (is it a scan?).",
              indexed_at: null,
            }),
            knowledgeDocument(),
          ],
        }),
      ),
    );

    // When I open Company knowledge
    renderScreen(<KnowledgeScreen />);

    // Then it shows as an error with its reason
    const scan = within(await screen.findByRole("row", { name: "Scan of the insurance policy" }));
    expect(scan.getByText("Error")).toBeInTheDocument();
    expect(scan.getByText("No text found in this PDF (is it a scan?).")).toBeInTheDocument();
  });

  it("shows a document still being processed", async () => {
    // Given a document being indexed
    server.use(
      handlers.knowledge(
        knowledgeBase({
          documents: [knowledgeDocument({ status: "processing", pages: null, indexed_at: null })],
        }),
      ),
    );

    // When I open Company knowledge
    renderScreen(<KnowledgeScreen />);

    // Then its status says so
    const register = within(
      await screen.findByRole("row", { name: "Commercial register extract" }),
    );
    expect(register.getByText("Processing")).toBeInTheDocument();
  });

  it("explains that the AI needs documents when there are none", async () => {
    // Given an empty knowledge base
    server.use(handlers.knowledge(knowledgeBase({ documents: [], last_indexed_at: null })));

    // When I open Company knowledge
    renderScreen(<KnowledgeScreen />);

    // Then I am told what to do
    expect(await screen.findByRole("heading", { name: "No documents yet" })).toBeInTheDocument();
    expect(screen.getByText("No documents")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("lets me retry when the documents could not be loaded", async () => {
    // Given the back fails once
    server.use(handlers.error("/knowledge", 500));
    const user = userEvent.setup();
    renderScreen(<KnowledgeScreen />);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("We couldn't load your company knowledge.")).toBeInTheDocument();

    // When the back is back and I retry
    server.use(handlers.knowledge(knowledgeBase()));
    await user.click(within(alert).getByRole("button", { name: "Try again" }));

    // Then the documents show
    expect(await screen.findByRole("table", { name: "Documents" })).toBeInTheDocument();
  });
});

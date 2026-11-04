import { screen, within } from "@testing-library/react";
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

  it("opens the original of a document", async () => {
    // Given the seeded knowledge base
    server.use(handlers.knowledge(knowledgeBase()));

    // When I open Company knowledge
    renderScreen(<KnowledgeScreen />);

    // Then a document's name links to its file
    const register = within(
      await screen.findByRole("row", { name: "Commercial register extract" }),
    );
    expect(register.getByRole("link", { name: "Commercial register extract" })).toHaveAttribute(
      "href",
      "http://localhost:8000/knowledge/documents/1/file",
    );
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

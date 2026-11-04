import { fireEvent, screen, waitFor, within } from "@testing-library/react";
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

  describe("adding documents", () => {
    const uvg = knowledgeDocument({
      id: 12,
      name: "UVG certificate",
      file_name: "UVG certificate.pdf",
      pages: null,
      status: "processing",
      indexed_at: null,
      created_at: "2026-11-04T14:10:00Z",
    });
    const pdf = (name: string) => new File(["%PDF-1.7"], name, { type: "application/pdf" });
    // The polling interval is 1 s: give the final status a little longer to show up.
    const POLLED = { timeout: 3000 };

    /** A back that indexes (or fails) the added document by the next refresh of the list. */
    function backIndexing(final: typeof uvg) {
      let stage: "before" | "processing" | "done" = "before";
      const added = handlers.addDocuments(() => {
        stage = "processing";
        return [uvg];
      });
      server.use(
        added.handler,
        handlers.knowledge(() => {
          const base = knowledgeBase();
          if (stage === "before") return base;
          const document = stage === "processing" ? uvg : final;
          stage = "done";
          return { ...base, documents: [document, ...base.documents] };
        }),
      );
      return added;
    }

    it("shows an added document as processing, then indexed", async () => {
      // Given a back that indexes what I add
      const added = backIndexing({
        ...uvg,
        status: "indexed",
        pages: 1,
        indexed_at: "2026-11-04T14:10:03Z",
      });
      const user = userEvent.setup();
      renderScreen(<KnowledgeScreen />);
      await screen.findByRole("table", { name: "Documents" });

      // When I add a PDF
      await user.upload(
        screen.getByLabelText("Choose PDF or Word documents"),
        pdf("UVG certificate.pdf"),
      );

      // Then it is listed at once as being processed
      const row = within(await screen.findByRole("row", { name: "UVG certificate" }));
      expect(row.getByText("Processing")).toBeInTheDocument();
      expect(row.getByText("Reading and indexing…")).toBeInTheDocument();
      expect(added.requests).toEqual([
        { contentType: expect.stringMatching(/^multipart\/form-data; boundary=/) },
      ]);
      // And it turns indexed without reloading the page
      expect(await row.findByText("Indexed", {}, POLLED)).toBeInTheDocument();
      expect(row.getByText("1 page")).toBeInTheDocument();
      expect(screen.getByText(/^3 documents/)).toBeInTheDocument();
    });

    it("tells me when an added file could not be read", async () => {
      // Given a back that cannot read what I add
      backIndexing({ ...uvg, status: "error", error: "This file is not a readable PDF." });
      const user = userEvent.setup();
      renderScreen(<KnowledgeScreen />);
      await screen.findByRole("table", { name: "Documents" });

      // When I add it
      await user.upload(
        screen.getByLabelText("Choose PDF or Word documents"),
        pdf("UVG certificate.pdf"),
      );

      // Then it ends in error with the reason
      const row = within(await screen.findByRole("row", { name: "UVG certificate" }));
      expect(await row.findByText("Error", {}, POLLED)).toBeInTheDocument();
      expect(row.getByText("This file is not a readable PDF.")).toBeInTheDocument();
    });

    it("sends several files at once", async () => {
      // Given a back that stores what I add
      const added = backIndexing({ ...uvg, status: "indexed" });
      const user = userEvent.setup();
      renderScreen(<KnowledgeScreen />);
      await screen.findByRole("table", { name: "Documents" });

      // When I choose two files
      await user.upload(screen.getByLabelText("Choose PDF or Word documents"), [
        pdf("UVG certificate.pdf"),
        pdf("VAT statement.pdf"),
      ]);

      // Then both go in one request
      await screen.findByRole("row", { name: "UVG certificate" });
      expect(added.requests).toHaveLength(1);
    });

    it("tells me why files were refused, and lets me dismiss it", async () => {
      // Given a back that refuses the file
      server.use(
        handlers.knowledge(knowledgeBase()),
        handlers.error("/knowledge/documents", 422, "big.pdf is larger than 20 MB.", "post"),
      );
      const user = userEvent.setup();
      renderScreen(<KnowledgeScreen />);
      await screen.findByRole("table", { name: "Documents" });

      // When I add it
      await user.upload(screen.getByLabelText("Choose PDF or Word documents"), pdf("big.pdf"));

      // Then I see why, and nothing was added
      const alert = await screen.findByRole("alert");
      expect(within(alert).getByText("These documents could not be added")).toBeInTheDocument();
      expect(within(alert).getByText("big.pdf is larger than 20 MB.")).toBeInTheDocument();
      expect(documents().getAllByRole("row")).toHaveLength(3);
      await user.click(within(alert).getByRole("button", { name: "Dismiss" }));
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("says it in plain words when adding fails on our side", async () => {
      // Given the back fails
      server.use(
        handlers.knowledge(knowledgeBase()),
        handlers.error("/knowledge/documents", 500, "Internal Server Error", "post"),
      );
      const user = userEvent.setup();
      renderScreen(<KnowledgeScreen />);
      await screen.findByRole("table", { name: "Documents" });

      // When I add a file
      await user.upload(
        screen.getByLabelText("Choose PDF or Word documents"),
        pdf("UVG certificate.pdf"),
      );

      // Then the message is not technical
      const alert = await screen.findByRole("alert");
      expect(
        within(alert).getByText("Something went wrong on our side. Please try again in a moment."),
      ).toBeInTheDocument();
      expect(within(alert).queryByText("Internal Server Error")).not.toBeInTheDocument();
    });

    // user-event cannot drag files from outside the page: drag events are fired directly (the one
    // allowed use of fireEvent, see the screen-tests skill).
    const dragFiles = (files: File[]) => ({ dataTransfer: { types: ["Files"], files } });

    it("adds the files I drop anywhere on the page", async () => {
      // Given a back that indexes what I add
      const added = backIndexing({ ...uvg, status: "indexed", pages: 1 });
      renderScreen(<KnowledgeScreen />);
      const page = await screen.findByRole("heading", { level: 1, name: "Alpenlogic AG" });

      // When I drag a PDF over the page, the drop zone tells me to release it
      const files = [pdf("UVG certificate.pdf")];
      fireEvent.dragEnter(page, dragFiles(files));
      const zone = within(screen.getByRole("region", { name: "Drop documents here" }));
      expect(zone.getByText("Release to add them")).toBeInTheDocument();

      // And when I drop it, it is added like with the button
      fireEvent.drop(page, dragFiles(files));
      expect(zone.queryByText("Release to add them")).not.toBeInTheDocument();
      const row = within(await screen.findByRole("row", { name: "UVG certificate" }));
      expect(row.getByText("Processing")).toBeInTheDocument();
      expect(added.requests).toHaveLength(1);
      expect(await row.findByText("Indexed", {}, POLLED)).toBeInTheDocument();
    });

    it("calms the drop zone down when the files leave without being dropped", async () => {
      // Given the seeded knowledge base
      server.use(handlers.knowledge(knowledgeBase()));
      renderScreen(<KnowledgeScreen />);
      const page = await screen.findByRole("heading", { level: 1, name: "Alpenlogic AG" });
      const table = screen.getByRole("table", { name: "Documents" });

      // When files are dragged across the page (entering a child element too), then leave it
      const files = [pdf("UVG certificate.pdf")];
      fireEvent.dragEnter(page, dragFiles(files));
      fireEvent.dragEnter(table, dragFiles(files));
      fireEvent.dragLeave(page, dragFiles(files));
      expect(screen.getByText("Release to add them")).toBeInTheDocument();
      fireEvent.dragLeave(table, dragFiles(files));

      // Then the drop zone is back to its invitation
      expect(screen.queryByText("Release to add them")).not.toBeInTheDocument();
      expect(screen.getByText(/Drop PDF or Word documents here/)).toBeInTheDocument();
    });

    it("ignores text or links dragged inside the page", async () => {
      // Given the seeded knowledge base
      server.use(handlers.knowledge(knowledgeBase()));
      renderScreen(<KnowledgeScreen />);
      const page = await screen.findByRole("heading", { level: 1, name: "Alpenlogic AG" });

      // When I drag some text over the page
      fireEvent.dragEnter(page, { dataTransfer: { types: ["text/plain"], files: [] } });

      // Then the drop zone does not react
      expect(screen.queryByText("Release to add them")).not.toBeInTheDocument();
    });

    it("shows where to drop documents, below the ones already there", async () => {
      // Given documents already indexed
      server.use(handlers.knowledge(knowledgeBase()));
      renderScreen(<KnowledgeScreen />);

      // Then a drop zone sits right below the list, with a way to browse instead
      const zone = await screen.findByRole("region", { name: "Drop documents here" });
      expect(zone).toHaveTextContent("Drop PDF or Word documents here, or browse your files");
      expect(zone).toHaveTextContent("PDF or DOCX · up to 20 MB each");
      expect(within(zone).getByRole("button", { name: "browse your files" })).toBeEnabled();
      const table = screen.getByRole("table", { name: "Documents" });
      expect(zone.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
    });

    it("makes the empty page itself the drop zone", async () => {
      // Given no document yet
      server.use(handlers.knowledge(knowledgeBase({ documents: [], last_indexed_at: null })));
      renderScreen(<KnowledgeScreen />);

      // Then the explanation and the invitation to drop are one zone
      const zone = within(await screen.findByRole("region", { name: "Drop documents here" }));
      expect(zone.getByRole("heading", { name: "No documents yet" })).toBeInTheDocument();
      expect(
        zone.getByText("The AI answers only from your company documents."),
      ).toBeInTheDocument();
      expect(zone.getByRole("button", { name: "browse your files" })).toBeInTheDocument();
    });

    it("only offers PDF and Word documents in the file picker", async () => {
      // Given the seeded knowledge base
      server.use(handlers.knowledge(knowledgeBase()));
      renderScreen(<KnowledgeScreen />);
      await screen.findByRole("table", { name: "Documents" });

      // Then the picker accepts PDF and DOCX, several at once
      const picker = screen.getByLabelText("Choose PDF or Word documents");
      expect(picker).toHaveAttribute("accept", ".pdf,.docx");
      expect(picker).toHaveAttribute("multiple");
      expect(screen.getByRole("button", { name: "Add documents" })).toBeEnabled();
    });
  });

  describe("deleting a document", () => {
    it("deletes a document once I confirm", async () => {
      // Given two documents; after the deletion, the back lists only the other one
      let deletedOnBack = false;
      const removal = handlers.deleteDocument();
      server.use(
        removal.handler,
        handlers.knowledge(() =>
          deletedOnBack
            ? knowledgeBase({ documents: knowledgeBase().documents.slice(1) })
            : knowledgeBase(),
        ),
      );
      const user = userEvent.setup();
      renderScreen(<KnowledgeScreen />);

      // When I delete the register extract and confirm
      await user.click(
        await screen.findByRole("button", { name: "Delete Commercial register extract" }),
      );
      const confirm = await screen.findByRole("alertdialog", {
        name: "Delete Commercial register extract?",
      });
      expect(
        within(confirm).getByText(
          "The AI will no longer answer from this document, and its file is removed. This can't be undone.",
        ),
      ).toBeInTheDocument();
      deletedOnBack = true;
      await user.click(within(confirm).getByRole("button", { name: "Delete document" }));

      // Then it leaves the list and the back deleted it
      await waitFor(() =>
        expect(
          screen.queryByRole("row", { name: "Commercial register extract" }),
        ).not.toBeInTheDocument(),
      );
      expect(removal.deleted).toEqual([1]);
      expect(screen.getByRole("row", { name: "Annual report 2024" })).toBeInTheDocument();
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    });

    it("keeps the document when I cancel", async () => {
      // Given the seeded knowledge base
      const removal = handlers.deleteDocument();
      server.use(removal.handler, handlers.knowledge(knowledgeBase()));
      const user = userEvent.setup();
      renderScreen(<KnowledgeScreen />);

      // When I ask to delete, then cancel
      await user.click(
        await screen.findByRole("button", { name: "Delete Commercial register extract" }),
      );
      const confirm = await screen.findByRole("alertdialog");
      await user.click(within(confirm).getByRole("button", { name: "Cancel" }));

      // Then nothing was deleted
      await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
      expect(screen.getByRole("row", { name: "Commercial register extract" })).toBeInTheDocument();
      expect(removal.deleted).toEqual([]);
    });

    it("brings the document back and tells me when it could not be deleted", async () => {
      // Given a back that fails to delete
      server.use(
        handlers.knowledge(knowledgeBase()),
        handlers.error("/knowledge/documents/1", 500, "Internal Server Error", "delete"),
      );
      const user = userEvent.setup();
      renderScreen(<KnowledgeScreen />);

      // When I delete a document
      await user.click(
        await screen.findByRole("button", { name: "Delete Commercial register extract" }),
      );
      await user.click(
        within(await screen.findByRole("alertdialog")).getByRole("button", {
          name: "Delete document",
        }),
      );

      // Then it is still listed, and I am told in plain words
      const alert = await screen.findByRole("alert");
      expect(
        within(alert).getByText("Commercial register extract could not be deleted"),
      ).toBeInTheDocument();
      expect(
        within(alert).getByText("Something went wrong on our side. Please try again in a moment."),
      ).toBeInTheDocument();
      expect(
        await screen.findByRole("row", { name: "Commercial register extract" }),
      ).toBeInTheDocument();
    });
  });
});

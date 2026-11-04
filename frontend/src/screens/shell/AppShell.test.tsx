import { screen, within } from "@testing-library/react";
import { freezeToday, handlers, renderScreen, server } from "@/shared/test";
import { tenderSummary } from "@/shared/test/fixtures";
import { AppShell } from "./AppShell";

describe("App shell", () => {
  beforeEach(() => freezeToday("2026-11-03"));

  it("lists the open tenders with the time left, next to the page content", async () => {
    // Given one open tender
    server.use(handlers.tenders([tenderSummary()]));

    // When any page renders inside the shell
    renderScreen(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );

    // Then the sidebar links to the tender and shows its days left
    const active = within(await screen.findByRole("list", { name: "Active tenders" }));
    const link = await active.findByRole("link", { name: /Cloud Platform Services/ });
    expect(link).toHaveAttribute("href", "/tenders/1");
    expect(active.getByText("16 days")).toBeInTheDocument();
    expect(screen.getByText("Page content")).toBeInTheDocument();
    expect(screen.getByText("Marc Keller")).toBeInTheDocument();
  });

  it("links to the tenders and to the company knowledge", async () => {
    // Given one open tender
    server.use(handlers.tenders([tenderSummary()]));

    // When any page renders inside the shell
    renderScreen(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );

    // Then the main navigation leads to both sections
    const nav = within(screen.getByRole("list", { name: "Main" }));
    expect(nav.getByRole("link", { name: "Tenders" })).toHaveAttribute("href", "/");
    expect(nav.getByRole("link", { name: "Company knowledge" })).toHaveAttribute(
      "href",
      "/knowledge",
    );
    expect(
      await screen.findByRole("link", { name: /Cloud Platform Services/ }),
    ).toBeInTheDocument();
  });
});

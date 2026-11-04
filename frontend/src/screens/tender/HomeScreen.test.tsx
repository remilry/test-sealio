import { screen } from "@testing-library/react";
import { freezeToday, handlers, renderScreen, server } from "@/shared/test";
import { knowledgeBase, tender, tenderSummary } from "@/shared/test/fixtures";
import { HomeScreen } from "./HomeScreen";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

describe("Home", () => {
  beforeEach(() => freezeToday("2026-11-03"));

  it("opens the first open tender directly", async () => {
    // Given one open tender
    server.use(
      handlers.tenders([tenderSummary()]),
      handlers.tender(tender()),
      handlers.knowledge(knowledgeBase()),
    );

    // When I land on the app
    renderScreen(<HomeScreen />);

    // Then I am on that tender, with its forms
    expect(
      await screen.findByRole("heading", { level: 1, name: /Cloud Platform Services/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Forms to complete" })).toBeInTheDocument();
  });

  it("says so when there is no open tender", async () => {
    // Given no tender
    server.use(handlers.tenders([]));

    // When I land on the app
    renderScreen(<HomeScreen />);

    // Then I see an empty state
    expect(await screen.findByRole("heading", { name: "No open tenders" })).toBeInTheDocument();
  });
});

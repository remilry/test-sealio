import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { handlers, renderScreen, server } from "@/shared/test";
import { DevResetButton } from "./DevResetButton";

describe("Dev reset button", () => {
  it("resets the demo after confirmation, then reloads on Company knowledge", async () => {
    // Given the API answers the reset
    const { handler, state } = handlers.resetDemo();
    server.use(handler);
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    const user = userEvent.setup();
    renderScreen(<DevResetButton />);

    // When the user clicks the floating button, then cancels
    await user.click(screen.getByRole("button", { name: "Reset demo" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    // Then nothing is reset
    expect(state.resets).toBe(0);

    // When they confirm
    await user.click(screen.getByRole("button", { name: "Reset demo" }));
    await user.click(await screen.findByRole("button", { name: "Reset" }));

    // Then the demo is reset once and the page reloads on Company knowledge
    await waitFor(() => expect(assign).toHaveBeenCalledWith("/knowledge"));
    expect(state.resets).toBe(1);
    vi.unstubAllGlobals();
  });
});

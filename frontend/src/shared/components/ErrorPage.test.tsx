import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderScreen } from "@/shared/test";
import { ErrorPage } from "./ErrorPage";

describe("Error page", () => {
  it("says in plain words that the page couldn't be shown, and lets me try again", async () => {
    // Given a screen that crashed
    const retry = vi.fn();
    renderScreen(<ErrorPage onRetry={retry} />);

    // Then I read what happened, without technical details
    expect(
      screen.getByRole("heading", { name: "This page couldn't be shown" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Something went wrong on our side. Please try again in a moment."),
    ).toBeInTheDocument();

    // And Try again reloads it
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});

import { screen } from "@testing-library/react";
import { useQuery } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { renderScreen, server } from "@/shared/test";

// Tooling check: rendering + TanStack Query + MSW work together. Replaced by real screen tests.
function Greeting() {
  const { data } = useQuery({
    queryKey: ["greeting"],
    queryFn: async () =>
      (await fetch("http://api.test/greeting")).json() as Promise<{ text: string }>,
  });
  return <p>{data?.text ?? "Loading…"}</p>;
}

describe("renderScreen", () => {
  it("shows data served by the mocked back", async () => {
    server.use(http.get("http://api.test/greeting", () => HttpResponse.json({ text: "Hello" })));
    renderScreen(<Greeting />);

    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(await screen.findByText("Hello")).toBeInTheDocument();
  });
});

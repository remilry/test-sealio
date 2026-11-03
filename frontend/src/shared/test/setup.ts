import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { server } from "./server";

// Any request without a handler fails the test: the network is always explicit.
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());

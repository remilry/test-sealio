import { ApiError } from "./errors";
import { isTransient, retryDelay, retryQuery, retryWrite } from "./retry";

describe("isTransient", () => {
  it("is true for a network failure and a server error", () => {
    expect(isTransient(new TypeError("Failed to fetch"))).toBe(true);
    expect(isTransient(new ApiError(503, "Service Unavailable"))).toBe(true);
    expect(isTransient(new ApiError(500, "Boom"))).toBe(true);
  });

  it("is false for a refusal, a missing page and a cancelled request", () => {
    expect(isTransient(new ApiError(404, "Not Found"))).toBe(false);
    expect(isTransient(new ApiError(422, "Invalid"))).toBe(false);
    expect(isTransient(new ApiError(409, "Conflict"))).toBe(false);
    expect(isTransient(new DOMException("", "AbortError"))).toBe(false);
  });
});

describe("retryQuery and retryWrite", () => {
  it("retries a read up to 3 times, a write up to 2, passing failures only", () => {
    const failure = new ApiError(500, "Boom");
    expect(retryQuery(2, failure)).toBe(true);
    expect(retryQuery(3, failure)).toBe(false);
    expect(retryWrite(1, failure)).toBe(true);
    expect(retryWrite(2, failure)).toBe(false);
    expect(retryQuery(0, new ApiError(404, "Not Found"))).toBe(false);
    expect(retryWrite(0, new ApiError(422, "Invalid"))).toBe(false);
  });
});

describe("retryDelay", () => {
  it("does not wait in tests", () => {
    expect([retryDelay(0), retryDelay(1), retryDelay(5)]).toEqual([0, 0, 0]);
  });
});

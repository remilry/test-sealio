import type { ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { delay, http, HttpResponse } from "msw";
import { API_URL } from "@/shared/api";
import { act } from "@testing-library/react";
import { handlers, server } from "@/shared/test";
import { answer, fillState } from "@/shared/test/fixtures";
import type { FillEvent } from "./fill-events";
import type { FillState } from "./fill-session.api";
import { fillKeys, useFillRun, useSaveAnswer } from "./fill-session.queries";

const counts = { fillable: 3, filled: 1, empty: 2, doubts: 0 };
const answered = (id: number, value: string, resolved_by: "ai" | "user" = "ai"): FillEvent => ({
  id: 10 + id,
  type: "field",
  field_id: id,
  state: "answered",
  answer: { ...answer(id, value), resolved_by },
  counts,
});

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, wrapper };
}

describe("useFillRun", () => {
  it("writes each answer into the cache as it arrives and replays on a new visit", async () => {
    // Given a run that already sent a phase and an answer
    const stream = handlers.fillEvents(1);
    server.use(stream.handler);
    const { queryClient, wrapper } = setup();
    queryClient.setQueryData(fillKeys.answers(1), fillState([]));
    stream.send({ id: 1, type: "phase", phase: "detecting_fields", to_answer: 3 });
    stream.send(answered(2, "Alpenlogic AG"));

    // When I follow it
    const { result, unmount } = renderHook(() => useFillRun(1, { follow: true }), { wrapper });

    // Then the replayed events fill the run and the cache
    await waitFor(() => expect(result.current.answered.has(2)).toBe(true));
    expect(result.current.toAnswer).toBe(3);
    expect(queryClient.getQueryData<FillState>(fillKeys.answers(1))?.answers[0]?.value).toBe(
      "Alpenlogic AG",
    );
    expect(queryClient.getQueryData<FillState>(fillKeys.answers(1))?.counts).toEqual(counts);

    // And a later visit gets the same events again
    unmount();
    const again = renderHook(() => useFillRun(1, { follow: true }), { wrapper });
    await waitFor(() => expect(again.result.current.answered.has(2)).toBe(true));
    stream.close();
  });

  it("keeps the value the user typed", async () => {
    // Given the user typed a value for field 2
    const stream = handlers.fillEvents(1);
    server.use(stream.handler);
    const { queryClient, wrapper } = setup();
    queryClient.setQueryData(fillKeys.answers(1), fillState([answer(2, "My value")]));

    // When the AI answers that field and field 3
    renderHook(() => useFillRun(1, { follow: true }), { wrapper });
    stream.send(answered(2, "AI value"));
    stream.send(answered(3, "Other"));

    // Then only the other field is written
    await waitFor(() =>
      expect(queryClient.getQueryData<FillState>(fillKeys.answers(1))?.answers).toHaveLength(2),
    );
    const values = queryClient
      .getQueryData<FillState>(fillKeys.answers(1))
      ?.answers.map((a) => a.value);
    expect(values).toEqual(["My value", "Other"]);
    stream.close();
  });

  it("refreshes the answers and the tender when the run ends", async () => {
    const stream = handlers.fillEvents(1);
    server.use(stream.handler);
    const { queryClient, wrapper } = setup();
    queryClient.setQueryData(fillKeys.answers(1), fillState([]));
    queryClient.setQueryData(["tenders", 1], { id: 1 });

    const { result } = renderHook(() => useFillRun(1, { follow: true }), { wrapper });
    stream.send({ id: 1, type: "done", filled: 1, fillable: 3, doubts: 0, seconds: 5 });
    stream.close();

    await waitFor(() => expect(result.current.outcome?.kind).toBe("done"));
    expect(queryClient.getQueryState(["tenders", 1])?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(fillKeys.answers(1))?.isInvalidated).toBe(true);
  });
});

describe("useFillRun when the stream stops early", () => {
  it("refetches and reconnects when the stream closes without done", async () => {
    // Given a stream that ends at once, without done (e.g. discarded from another tab)
    let connections = 0;
    server.use(
      http.get(`${API_URL}/forms/1/fill/events`, () => {
        connections += 1;
        return new HttpResponse("", { headers: { "content-type": "text/event-stream" } });
      }),
    );
    const { queryClient, wrapper } = setup();
    queryClient.setQueryData(fillKeys.answers(1), fillState([]));
    queryClient.setQueryData(["tenders", 1], { id: 1 });

    renderHook(() => useFillRun(1, { follow: true }), { wrapper });

    await waitFor(() =>
      expect(queryClient.getQueryState(["tenders", 1])?.isInvalidated).toBe(true),
    );
    expect(queryClient.getQueryState(fillKeys.answers(1))?.isInvalidated).toBe(true);
    await waitFor(() => expect(connections).toBeGreaterThan(1), { timeout: 2000 });
  });

  it("refetches without an unhandled rejection when the stream answers an error", async () => {
    server.use(handlers.error("/forms/1/fill/events", 500));
    const { queryClient, wrapper } = setup();
    queryClient.setQueryData(fillKeys.answers(1), fillState([]));
    queryClient.setQueryData(["tenders", 1], { id: 1 });

    renderHook(() => useFillRun(1, { follow: true }), { wrapper });

    await waitFor(() =>
      expect(queryClient.getQueryState(["tenders", 1])?.isInvalidated).toBe(true),
    );
    expect(queryClient.getQueryState(fillKeys.answers(1))?.isInvalidated).toBe(true);
  });
});

describe("useSaveAnswer with streamed answers", () => {
  it("keeps an answer streamed in meanwhile when the save fails", async () => {
    server.use(
      http.patch(`${API_URL}/forms/1/fields/2`, async () => {
        await delay(100);
        return HttpResponse.json({ detail: "nope" }, { status: 500 });
      }),
    );
    const { queryClient, wrapper } = setup();
    queryClient.setQueryData(fillKeys.answers(1), fillState([]));
    const { result } = renderHook(() => useSaveAnswer(1), { wrapper });

    act(() => result.current.mutate({ fieldId: 2, value: "mine" }));
    await waitFor(() =>
      expect(queryClient.getQueryData<FillState>(fillKeys.answers(1))?.answers).toHaveLength(1),
    );
    queryClient.setQueryData<FillState>(fillKeys.answers(1), (state) => ({
      ...state!,
      answers: [...state!.answers, answer(3, "streamed")],
    }));
    await waitFor(() => expect(result.current.isError).toBe(true));

    const values = queryClient
      .getQueryData<FillState>(fillKeys.answers(1))
      ?.answers.map((a) => [a.field_id, a.value]);
    expect(values).toEqual([[3, "streamed"]]);
  });

  it("keeps an answer streamed in meanwhile when the save succeeds", async () => {
    server.use(
      http.patch(`${API_URL}/forms/1/fields/2`, async () => {
        await delay(100);
        return HttpResponse.json(fillState([answer(2, "mine")]));
      }),
    );
    const { queryClient, wrapper } = setup();
    queryClient.setQueryData(fillKeys.answers(1), fillState([]));
    const { result } = renderHook(() => useSaveAnswer(1), { wrapper });

    act(() => result.current.mutate({ fieldId: 2, value: "mine" }));
    queryClient.setQueryData<FillState>(fillKeys.answers(1), (state) => ({
      ...state!,
      answers: [...state!.answers, answer(3, "streamed")],
    }));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const values = queryClient
      .getQueryData<FillState>(fillKeys.answers(1))
      ?.answers.map((a) => [a.field_id, a.value]);
    expect(values).toHaveLength(2);
    expect(values).toContainEqual([2, "mine"]);
    expect(values).toContainEqual([3, "streamed"]);
  });
});

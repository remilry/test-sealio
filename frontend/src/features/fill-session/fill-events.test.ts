import { initialRun, reduceRun, type FillEvent } from "./fill-events";
import type { Answer } from "./fill-session.api";

const answer: Answer = {
  field_id: 2,
  value: "Alpenlogic AG",
  proposed_value: "Alpenlogic AG",
  resolved_by: "ai",
  resolved_at: "2026-11-04T10:00:00Z",
  type: "auto",
  candidates: [],
  user_only_reason: null,
  needs_review: false,
};
const counts = { fillable: 3, filled: 1, empty: 2, doubts: 0, open: 2 };

const events: FillEvent[] = [
  { id: 1, type: "phase", phase: "reading_form" },
  { id: 2, type: "phase", phase: "detecting_fields", to_answer: 3 },
  { id: 3, type: "phase", phase: "searching" },
  { id: 4, type: "field", field_id: 2, state: "searching" },
  { id: 5, type: "field", field_id: 2, state: "answered", answer, counts },
];

const play = (list: FillEvent[], from = initialRun) =>
  list.reduce((run, event, i) => reduceRun(run, event, 1000 + i), from);

describe("reduceRun", () => {
  it("follows the phase", () => {
    expect(play(events.slice(0, 1)).phase).toBe("reading_form");
  });

  it("records how many fields will be answered", () => {
    expect(play(events.slice(0, 2)).toAnswer).toBe(3);
  });

  it("marks a field as searching", () => {
    const run = play(events.slice(0, 4));
    expect([...run.searching]).toEqual([2]);
    expect(run.answered.size).toBe(0);
  });

  it("moves an answered field out of searching and notes the progress time", () => {
    const run = play(events);
    expect(run.searching.has(2)).toBe(false);
    expect(run.answered.has(2)).toBe(true);
    expect(run.lastProgressAt).toBe(1004);
  });

  it("gives the same run when the events are replayed after a reload", () => {
    const once = play(events);
    const twice = play(events, play(events));
    expect({ ...twice, lastProgressAt: 0 }).toEqual({ ...once, lastProgressAt: 0 });
  });

  it("ends with the outcome of the run", () => {
    const done = play([
      ...events,
      { id: 6, type: "done", filled: 1, fillable: 3, doubts: 0, seconds: 12 },
    ]);
    expect(done.outcome).toEqual({ kind: "done", filled: 1, fillable: 3, seconds: 12 });
    const failed = play([...events, { id: 6, type: "error", message: "boom" }]);
    expect(failed.outcome).toEqual({ kind: "error", message: "boom" });
  });

  it("stops searching every field when the run ends, even midway through a section", () => {
    const searching: FillEvent[] = [
      ...events,
      { id: 6, type: "field", field_id: 3, state: "searching" },
    ];
    expect(play([...searching, { id: 7, type: "error", message: "boom" }]).searching.size).toBe(0);
    const done = play([
      ...searching,
      { id: 7, type: "done", filled: 1, fillable: 3, doubts: 0, seconds: 12 },
    ]);
    expect(done.searching.size).toBe(0);
    expect(done.answered.has(2)).toBe(true);
  });

  it("keeps the value being written until the field's answer replaces it", () => {
    const writing: FillEvent[] = [
      ...events.slice(0, 4),
      { id: 5, type: "field", field_id: 2, state: "writing", text: "Alpen" },
      { id: 6, type: "field", field_id: 2, state: "writing", text: "Alpenlogic" },
    ];
    expect(play(writing).writing.get(2)).toBe("Alpenlogic");
    const answered = play([...writing, { ...events[4], id: 7 }]);
    expect(answered.writing.has(2)).toBe(false);
    // A late value being written never comes back over an answer.
    const late = play([
      ...writing,
      { ...events[4], id: 7 },
      { id: 8, type: "field", field_id: 2, state: "writing", text: "Alp" },
    ]);
    expect(late.writing.has(2)).toBe(false);
  });

  it("forgets the values being written when the run ends", () => {
    const writing: FillEvent[] = [
      ...events.slice(0, 4),
      { id: 5, type: "field", field_id: 2, state: "writing", text: "Alpen" },
    ];
    expect(play([...writing, { id: 6, type: "error", message: "boom" }]).writing.size).toBe(0);
  });
});

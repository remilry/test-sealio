import { describe, expect, it } from "vitest";
import type { QueueField } from "./FieldList";
import { groupFields, isOpen, nextOpen, reviewGroup, settledAs } from "./review";

let nextId = 1;
function field(overrides: Partial<QueueField> = {}): QueueField {
  return {
    id: nextId++,
    label: "Field",
    fillable: true,
    yesNo: false,
    value: null,
    unsaved: null,
    enteredAt: null,
    state: "answered",
    writing: null,
    type: null,
    resolvedBy: null,
    proposedValue: null,
    candidates: [],
    userOnlyReason: null,
    failed: false,
    ...overrides,
  };
}

const ai = (type: NonNullable<QueueField["type"]>, value: string | null) =>
  field({ type, value, proposedValue: value, resolvedBy: "ai" });
const candidate = (value: string) => ({
  value,
  citations: [],
  source_date: null,
  valid_until: null,
});

describe("reviewGroup", () => {
  it("puts conflicts, outdated and unsure values to check", () => {
    expect(reviewGroup(ai("conflict", "A"))).toBe("toCheck");
    expect(reviewGroup(ai("outdated", "A"))).toBe("toCheck");
    expect(reviewGroup(ai("unsure", "A"))).toBe("toCheck");
  });

  it("puts a suggested value to check, a field only I can fill without suggestion in No value", () => {
    expect(reviewGroup(ai("manual", "Zurich"))).toBe("toCheck");
    expect(reviewGroup(ai("manual", null))).toBe("noValue");
  });

  it("puts automatic answers and proven declarations in Filled automatically", () => {
    expect(reviewGroup(ai("auto", "A"))).toBe("automatic");
    expect(reviewGroup(ai("declaration", "yes"))).toBe("automatic");
  });

  it("puts a field not found or never answered in No value", () => {
    expect(reviewGroup(ai("missing", null))).toBe("noValue");
    expect(reviewGroup(field())).toBe("noValue");
  });

  it("keeps a settled doubt in its group, and leaves signatures out", () => {
    expect(reviewGroup({ ...ai("conflict", "A"), resolvedBy: "user" })).toBe("toCheck");
    expect(reviewGroup(field({ fillable: false }))).toBeNull();
  });
});

describe("isOpen", () => {
  it("is open while nobody settled a doubt or an empty field", () => {
    expect(isOpen(ai("outdated", "A"))).toBe(true);
    expect(isOpen(ai("missing", null))).toBe(true);
    expect(isOpen(field())).toBe(true);
    expect(isOpen(ai("auto", "A"))).toBe(false);
  });

  it("is settled once I saved it, even empty, and a signature is never open", () => {
    expect(isOpen({ ...ai("outdated", "A"), resolvedBy: "user" })).toBe(false);
    expect(isOpen(field({ resolvedBy: "user" }))).toBe(false);
    expect(isOpen(field({ fillable: false }))).toBe(false);
  });
});

describe("settledAs", () => {
  it("says I kept the proposed value or chose another source", () => {
    const conflict = { ...ai("conflict", "A"), candidates: [candidate("A"), candidate("B")] };
    expect(settledAs({ ...conflict, resolvedBy: "user" })).toBe("kept");
    expect(settledAs({ ...conflict, resolvedBy: "user", value: "B" })).toBe("kept");
  });

  it("says I entered my own value, or left the field empty", () => {
    expect(settledAs({ ...ai("outdated", "A"), resolvedBy: "user", value: "C" })).toBe("entered");
    expect(settledAs(field({ resolvedBy: "user", value: "C" }))).toBe("entered");
    expect(settledAs({ ...ai("missing", null), resolvedBy: "user" })).toBe("leftEmpty");
  });

  it("is nothing while the answer is still the automatic one", () => {
    expect(settledAs(ai("outdated", "A"))).toBeNull();
  });
});

describe("groupFields", () => {
  it("lists the three groups in order, each in form order, with what is left open", () => {
    const auto = ai("auto", "A");
    const missing = ai("missing", null);
    const outdated = ai("outdated", "A");
    const kept = { ...ai("conflict", "B"), resolvedBy: "user" as const };
    const signature = field({ fillable: false });

    const { groups, signatures } = groupFields([auto, missing, outdated, kept, signature]);

    expect(groups.map((g) => [g.group, g.fields.map((f) => f.id), g.open])).toEqual([
      ["toCheck", [outdated.id, kept.id], 1],
      ["noValue", [missing.id], 1],
      ["automatic", [auto.id], 0],
    ]);
    expect(signatures).toEqual([signature]);
  });

  it("keeps an empty group, so its count shows 0", () => {
    expect(groupFields([ai("auto", "A")]).groups.map((g) => g.fields.length)).toEqual([0, 0, 1]);
  });
});

describe("nextOpen", () => {
  const outdated = ai("outdated", "A");
  const kept = { ...ai("unsure", "B"), resolvedBy: "user" as const };
  const missing = ai("missing", null);
  const auto = ai("auto", "C");
  // Form order differs from queue order: the empty field comes first in the form.
  const fields = [missing, auto, outdated, kept];

  it("goes to the next open field in queue order, skipping settled ones", () => {
    expect(nextOpen(fields, outdated.id)).toBe(missing.id);
  });

  it("wraps around to the first open field", () => {
    expect(nextOpen(fields, missing.id)).toBe(outdated.id);
    expect(nextOpen(fields, auto.id)).toBe(outdated.id);
  });

  it("is null when nothing else is open", () => {
    expect(nextOpen([outdated, kept, auto], outdated.id)).toBeNull();
    expect(nextOpen([kept, auto], kept.id)).toBeNull();
  });
});

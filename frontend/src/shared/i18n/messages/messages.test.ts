import messages from "./en.json";

function texts(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (value && typeof value === "object") return Object.values(value).flatMap(texts);
  return [];
}

describe("English messages", () => {
  it("never mention AI: the interface speaks of automatic filling", () => {
    expect(texts(messages).filter((text) => /\bAI\b/.test(text))).toEqual([]);
  });
});

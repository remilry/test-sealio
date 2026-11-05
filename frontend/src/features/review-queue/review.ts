import type { QueueField } from "./FieldList";

/** The review queue's groups, in the order the user goes through them (doubts first). */
export type ReviewGroup = "toCheck" | "noValue" | "automatic";

export const REVIEW_GROUPS: readonly ReviewGroup[] = ["toCheck", "noValue", "automatic"];

/**
 * The group of a field, from what the automatic fill found (kept when the user saves the field,
 * so a field never moves when it is settled). Null for a signature, which is not reviewed.
 */
export function reviewGroup(field: QueueField): ReviewGroup | null {
  if (!field.fillable) return null;
  switch (field.type) {
    case "conflict":
    case "outdated":
    case "unsure":
      return "toCheck";
    case "manual":
      return field.proposedValue ? "toCheck" : "noValue";
    case "auto":
    case "declaration":
      return "automatic";
    default:
      return "noValue";
  }
}

/** Still to look at: nobody settled it, and it has no value or a value to check. */
export function isOpen(field: QueueField): boolean {
  if (!field.fillable || field.resolvedBy === "user") return false;
  return !field.value || reviewGroup(field) === "toCheck";
}

/** How the user settled the field, or null while it is not theirs. */
export function settledAs(field: QueueField): "kept" | "leftEmpty" | "entered" | null {
  if (field.resolvedBy !== "user") return null;
  if (!field.value) return "leftEmpty";
  const proposed = [field.proposedValue, ...field.candidates.map((c) => c.value)];
  return proposed.includes(field.value) ? "kept" : "entered";
}

export type QueueGroup = { group: ReviewGroup; fields: QueueField[]; open: number };

/** The three groups in order (empty ones included), form order inside; signatures apart. */
export function groupFields(fields: QueueField[]): {
  groups: QueueGroup[];
  signatures: QueueField[];
} {
  const groups = REVIEW_GROUPS.map((group) => {
    const inGroup = fields.filter((field) => reviewGroup(field) === group);
    return { group, fields: inGroup, open: inGroup.filter(isOpen).length };
  });
  return { groups, signatures: fields.filter((field) => !field.fillable) };
}

/** The next open field after `afterId` in queue order, wrapping around; null when none. */
export function nextOpen(fields: QueueField[], afterId: number): number | null {
  const queue = groupFields(fields).groups.flatMap((group) => group.fields);
  const index = queue.findIndex((field) => field.id === afterId);
  const rotated = [...queue.slice(index + 1), ...queue.slice(0, Math.max(index, 0))];
  return rotated.find((field) => field.id !== afterId && isOpen(field))?.id ?? null;
}

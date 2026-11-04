import { CheckIcon } from "lucide-react";
import { useSaveStatus } from "./fill-session.queries";

const LABELS = {
  idle: "All changes saved",
  saving: "Saving…",
  saved: "Saved",
  failed: "Couldn't save — press Enter in the field to try again",
} as const;

/** "✓ Saved" in the top bar: every edit is saved automatically. */
export function SaveIndicator({ formId }: { formId: number }) {
  const status = useSaveStatus(formId);
  return (
    <span
      role="status"
      className={
        status === "failed"
          ? "text-xs whitespace-nowrap text-destructive"
          : "flex items-center gap-1 text-xs whitespace-nowrap text-muted-foreground"
      }
    >
      {(status === "saved" || status === "idle") && <CheckIcon className="size-3" aria-hidden />}
      {LABELS[status]}
    </span>
  );
}

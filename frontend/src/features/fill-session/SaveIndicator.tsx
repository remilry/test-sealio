import { CheckIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSaveStatus } from "./fill-session.queries";

/** "✓ Saved" in the top bar: every edit is saved automatically. */
export function SaveIndicator({ formId }: { formId: number }) {
  const t = useTranslations("saveStatus");
  const status = useSaveStatus(formId);
  if (status === "failed") {
    return (
      <span role="status" className="text-xs whitespace-nowrap text-destructive">
        {t("failed")}
      </span>
    );
  }
  return (
    <span
      role="status"
      className="flex items-center gap-1 text-xs whitespace-nowrap text-muted-foreground"
    >
      {status !== "saving" && <CheckIcon className="size-3" aria-hidden />}
      {t(status)}
    </span>
  );
}

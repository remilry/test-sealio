import { useTranslations } from "next-intl";
import { daysUntil, formatDate, type IsoDate } from "@/shared/utils/date";

/** Wording of the time left before a deadline: "16 days", "due today", "closed". */
export function useDeadlineFormat() {
  const t = useTranslations("tender");
  const timeLeft = (days: number) => (days < 0 ? t("closed") : t("timeLeft", { days }));
  return {
    timeLeft,
    /** "19.11.2026 · 16 days" */
    deadline: (deadline: IsoDate) =>
      t("deadline", { date: formatDate(deadline), timeLeft: timeLeft(daysUntil(deadline)) }),
  };
}

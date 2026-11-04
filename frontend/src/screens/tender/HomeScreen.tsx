"use client";

import { InboxIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useTenders } from "@/features/tender";
import { EmptyState, LoadError } from "@/shared/components/LoadStates";
import { TenderScreen } from "./TenderScreen";

/** Landing page: there is one tender in the MVP, so open the most urgent one directly. */
export function HomeScreen() {
  const t = useTranslations("tender");
  const { data: tenders, isError, refetch } = useTenders();

  if (isError) {
    return (
      <div className="p-8">
        <LoadError title={t("listLoadError")} onRetry={() => void refetch()} />
      </div>
    );
  }
  // While the list loads, TenderScreen's own skeleton would flash twice: show nothing yet.
  if (!tenders) return null;
  if (tenders.length === 0) {
    return (
      <EmptyState title={t("noneTitle")} icon={<InboxIcon />}>
        {t("noneDescription")}
      </EmptyState>
    );
  }
  return <TenderScreen tenderId={tenders[0].id} />;
}

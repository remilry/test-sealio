"use client";

import { InboxIcon } from "lucide-react";
import { useTenders } from "@/features/tender";
import { LoadError, EmptyState } from "@/shared/components/LoadStates";
import { TenderScreen } from "./TenderScreen";

/** Landing page: there is one tender in the MVP, so open the most urgent one directly. */
export function HomeScreen() {
  const { data: tenders, isError, refetch } = useTenders();

  if (isError) {
    return (
      <div className="p-8">
        <LoadError title="We couldn't load your tenders." onRetry={() => void refetch()} />
      </div>
    );
  }
  // While the list loads, TenderScreen's own skeleton would flash twice: show nothing yet.
  if (!tenders) return null;
  if (tenders.length === 0) {
    return (
      <EmptyState title="No open tenders" icon={<InboxIcon />}>
        New calls for tenders appear here as soon as they are published.
      </EmptyState>
    );
  }
  return <TenderScreen tenderId={tenders[0].id} />;
}

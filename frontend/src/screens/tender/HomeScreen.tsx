"use client";

import { useQuery } from "@tanstack/react-query";
import { InboxIcon } from "lucide-react";
import { tenderQueries } from "@/features/tender";
import { Alert, AlertAction, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/shared/ui/empty";
import { TenderScreen } from "./TenderScreen";

/** Landing page: there is one tender in the MVP, so open the most urgent one directly. */
export function HomeScreen() {
  const { data: tenders, isError, refetch } = useQuery(tenderQueries.all());

  if (isError) {
    return (
      <div className="p-8">
        <Alert variant="destructive">
          <AlertTitle>We couldn&apos;t load your tenders.</AlertTitle>
          <AlertAction>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              Try again
            </Button>
          </AlertAction>
        </Alert>
      </div>
    );
  }
  if (tenders && tenders.length === 0) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <InboxIcon />
          </EmptyMedia>
          <EmptyTitle role="heading" aria-level={1}>
            No open tenders
          </EmptyTitle>
          <EmptyDescription>
            New calls for tenders appear here as soon as they are published.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  // While the list loads, TenderScreen's own skeleton would flash twice: show nothing yet.
  return tenders ? <TenderScreen tenderId={tenders[0].id} /> : null;
}

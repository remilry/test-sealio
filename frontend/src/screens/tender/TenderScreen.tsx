"use client";

import { useQuery } from "@tanstack/react-query";
import { FileQuestionIcon } from "lucide-react";
import { FormList, TenderHeader, tenderQueries } from "@/features/tender";
import { isNotFound } from "@/shared/api";
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/shared/ui/empty";
import { Skeleton } from "@/shared/ui/skeleton";

/** Tender detail: what is asked, when, and the forms to fill (docs/USER_FLOW.md §3.2). */
export function TenderScreen({ tenderId }: { tenderId: number }) {
  const { data: tender, error, isPending, refetch } = useQuery(tenderQueries.detail(tenderId));

  return (
    <div className="flex flex-1 flex-col">
      <div className="sticky top-0 z-10 flex h-13 items-center gap-2 border-b bg-card px-6">
        <span className="text-muted-foreground">Tenders</span>
        {tender && (
          <>
            <span className="text-border">/</span>
            <span className="truncate font-medium">{tender.title}</span>
          </>
        )}
      </div>
      <div className="mx-auto flex w-full max-w-290 flex-col gap-6 px-8 pt-7 pb-24">
        {isPending ? (
          <TenderSkeleton />
        ) : error ? (
          isNotFound(error) ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <FileQuestionIcon />
                </EmptyMedia>
                <EmptyTitle role="heading" aria-level={1}>
                  Tender not found
                </EmptyTitle>
                <EmptyDescription>It may have been withdrawn by the buyer.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <Alert variant="destructive">
              <AlertTitle>We couldn&apos;t load this tender.</AlertTitle>
              <AlertDescription>Check that the API is running, then try again.</AlertDescription>
              <AlertAction>
                <Button variant="outline" size="sm" onClick={() => refetch()}>
                  Try again
                </Button>
              </AlertAction>
            </Alert>
          )
        ) : (
          <>
            <TenderHeader tender={tender} />
            <FormList forms={tender.forms} />
          </>
        )}
      </div>
    </div>
  );
}

function TenderSkeleton() {
  return (
    <div aria-label="Loading tender" className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
      </div>
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

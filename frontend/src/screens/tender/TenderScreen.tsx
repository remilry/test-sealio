"use client";

import type { ReactNode } from "react";
import { FormList, TenderHeader, useTender } from "@/features/tender";
import { isNotFound } from "@/shared/api";
import { LoadError, EmptyState } from "@/shared/components/LoadStates";
import { Skeleton } from "@/shared/ui/skeleton";

/** Tender detail: what is asked, when, and the forms to fill (docs/USER_FLOW.md §3.2). */
export function TenderScreen({ tenderId }: { tenderId: number }) {
  const { data: tender, error, isPending, refetch } = useTender(tenderId);

  if (isPending) {
    return (
      <TenderFrame>
        <TenderSkeleton />
      </TenderFrame>
    );
  }
  if (isNotFound(error)) {
    return (
      <TenderFrame>
        <EmptyState title="Tender not found">It may have been withdrawn by the buyer.</EmptyState>
      </TenderFrame>
    );
  }
  if (error) {
    return (
      <TenderFrame>
        <LoadError title="We couldn't load this tender." onRetry={() => void refetch()} />
      </TenderFrame>
    );
  }
  return (
    <TenderFrame title={tender.title}>
      <TenderHeader tender={tender} />
      <FormList forms={tender.forms} />
    </TenderFrame>
  );
}

/** The breadcrumb bar and the page column, whatever the state of the tender. */
function TenderFrame({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <div className="sticky top-0 z-10 flex h-13 items-center gap-2 border-b bg-card px-6">
        <span className="text-muted-foreground">Tenders</span>
        {title && (
          <>
            <span className="text-border">/</span>
            <span className="truncate font-medium">{title}</span>
          </>
        )}
      </div>
      <div className="mx-auto flex w-full max-w-290 flex-col gap-6 px-8 pt-7 pb-24">{children}</div>
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

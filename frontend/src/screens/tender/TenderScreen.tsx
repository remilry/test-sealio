"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { KnowledgeCard, useKnowledgeBase } from "@/features/knowledge-base";
import { FormList, TenderHeader, useTender } from "@/features/tender";
import { isNotFound } from "@/shared/api";
import { EmptyState, LoadError } from "@/shared/components/LoadStates";
import { FormAction } from "./FormAction";
import { Skeleton } from "@/shared/ui/skeleton";

/** Tender detail: what is asked, when, and the forms to fill (docs/USER_FLOW.md §3.2). */
export function TenderScreen({ tenderId }: { tenderId: number }) {
  const t = useTranslations("tender");
  const tCommon = useTranslations("common");
  const { data: tender, error, isPending, refetch } = useTender(tenderId);
  const { data: knowledge } = useKnowledgeBase();

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
        <EmptyState title={t("notFound")}>{tCommon("withdrawnByBuyer")}</EmptyState>
      </TenderFrame>
    );
  }
  if (error) {
    return (
      <TenderFrame>
        <LoadError title={t("loadError")} onRetry={() => void refetch()} />
      </TenderFrame>
    );
  }
  return (
    <TenderFrame title={tender.title}>
      <TenderHeader tender={tender} />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <FormList
          forms={tender.forms}
          renderAction={(form) => (
            <FormAction form={form} documentCount={knowledge?.documents.length} />
          )}
        />
        <aside className="lg:pt-8.5">
          <KnowledgeCard />
        </aside>
      </div>
    </TenderFrame>
  );
}

/** The breadcrumb bar and the page column, whatever the state of the tender. */
function TenderFrame({ title, children }: { title?: string; children: ReactNode }) {
  const t = useTranslations("tender");
  return (
    <div className="flex flex-1 flex-col">
      <div className="sticky top-0 z-10 flex h-13 items-center gap-2 border-b bg-card px-6">
        <span className="text-muted-foreground">{t("breadcrumbRoot")}</span>
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
  const t = useTranslations("tender");
  return (
    <div aria-label={t("loading")} className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
      </div>
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

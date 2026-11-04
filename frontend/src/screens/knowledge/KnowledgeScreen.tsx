"use client";

import { useState, type ReactNode } from "react";
import { LibraryIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import {
  AddDocumentsButton,
  AddDocumentsError,
  DocumentTable,
  useAddDocuments,
  useKnowledgeBase,
  type KnowledgeBase,
} from "@/features/knowledge-base";
import { EmptyState, LoadError } from "@/shared/components/LoadStates";
import { Skeleton } from "@/shared/ui/skeleton";
import { formatDay, formatTime } from "@/shared/utils/date";
import { DocumentPreviewDialog } from "./DocumentPreviewDialog";

/**
 * Company knowledge (docs/USER_FLOW.md §3.1): the documents the AI answers from, and whether
 * each one is indexed. V1 lists documents only (no facts extracted).
 */
export function KnowledgeScreen() {
  const t = useTranslations("knowledge");
  const { data: knowledge, error, isPending, refetch } = useKnowledgeBase();
  const add = useAddDocuments();

  if (isPending) {
    return (
      <KnowledgeFrame>
        <KnowledgeSkeleton />
      </KnowledgeFrame>
    );
  }
  if (error) {
    return (
      <KnowledgeFrame>
        <LoadError title={t("loadError")} onRetry={() => void refetch()} />
      </KnowledgeFrame>
    );
  }
  return (
    <KnowledgeFrame actions={<AddDocumentsButton add={add} />}>
      <header className="flex flex-col gap-1">
        <h1 className="text-[22px] font-semibold tracking-tight">{knowledge.company_name}</h1>
        <Summary knowledge={knowledge} />
      </header>
      <AddDocumentsError add={add} />
      <Documents knowledge={knowledge} />
    </KnowledgeFrame>
  );
}

function Summary({ knowledge }: { knowledge: KnowledgeBase }) {
  const t = useTranslations("knowledge");
  const count = knowledge.documents.length;
  if (!knowledge.last_indexed_at) {
    return <p className="text-muted-foreground">{t("summary", { count })}</p>;
  }
  return (
    <p className="text-muted-foreground">
      {t("summaryIndexed", {
        count,
        date: formatDay(knowledge.last_indexed_at),
        time: formatTime(knowledge.last_indexed_at),
      })}
    </p>
  );
}

function Documents({ knowledge }: { knowledge: KnowledgeBase }) {
  const t = useTranslations("knowledge");
  const [openedId, setOpenedId] = useState<number | null>(null);
  const opened = knowledge.documents.find((document) => document.id === openedId) ?? null;
  if (knowledge.documents.length === 0) {
    return (
      <EmptyState icon={<LibraryIcon />} level={2} title={t("noneTitle")}>
        {t("noneDescription")}
      </EmptyState>
    );
  }
  return (
    <>
      <DocumentTable
        documents={knowledge.documents}
        onOpen={(document) => setOpenedId(document.id)}
      />
      <DocumentPreviewDialog document={opened} onClose={() => setOpenedId(null)} />
    </>
  );
}

/** The top bar and the page column, whatever the state of the knowledge base. */
function KnowledgeFrame({ actions, children }: { actions?: ReactNode; children: ReactNode }) {
  const t = useTranslations("knowledge");
  return (
    <div className="flex flex-1 flex-col">
      <div className="sticky top-0 z-10 flex h-13 items-center gap-2 border-b bg-card px-6">
        <span className="font-medium">{t("breadcrumb")}</span>
        <div className="flex-1" />
        {actions}
      </div>
      <div className="mx-auto flex w-full max-w-275 flex-col gap-5 px-8 pt-7 pb-24">{children}</div>
    </div>
  );
}

function KnowledgeSkeleton() {
  const t = useTranslations("knowledge");
  return (
    <div aria-label={t("loading")} className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-4 w-72" />
      </div>
      <Skeleton className="h-96 w-full" />
    </div>
  );
}

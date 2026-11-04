"use client";

import { useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import {
  AddDocumentsButton,
  AddDocumentsError,
  DeleteDocumentError,
  DocumentDropZone,
  DocumentTable,
  useAddDocuments,
  useDeleteDocument,
  useDocumentPicker,
  useKnowledgeBase,
  type KnowledgeBase,
} from "@/features/knowledge-base";
import { FileDropArea } from "@/shared/components/FileDropArea";
import { LoadError } from "@/shared/components/LoadStates";
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
  const { picker, browse } = useDocumentPicker(add);
  const remove = useDeleteDocument();

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
    <KnowledgeFrame
      actions={<AddDocumentsButton add={add} onBrowse={browse} />}
      onDropFiles={add.isPending ? undefined : (files) => add.mutate(files)}
    >
      <header className="flex flex-col gap-1">
        <h1 className="text-[22px] font-semibold tracking-tight">{knowledge.company_name}</h1>
        <Summary knowledge={knowledge} />
      </header>
      {picker}
      <AddDocumentsError add={add} />
      <DeleteDocumentError remove={remove} />
      <Documents
        knowledge={knowledge}
        add={add}
        onBrowse={browse}
        onDelete={(document) => remove.mutate(document)}
      />
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

function Documents({
  knowledge,
  add,
  onBrowse,
  onDelete,
}: {
  knowledge: KnowledgeBase;
  add: ReturnType<typeof useAddDocuments>;
  onBrowse: () => void;
  onDelete: (document: KnowledgeBase["documents"][number]) => void;
}) {
  const [openedId, setOpenedId] = useState<number | null>(null);
  const opened = knowledge.documents.find((document) => document.id === openedId) ?? null;
  if (knowledge.documents.length === 0) {
    return <DocumentDropZone add={add} onBrowse={onBrowse} empty />;
  }
  return (
    <>
      <DocumentTable
        documents={knowledge.documents}
        onOpen={(document) => setOpenedId(document.id)}
        onDelete={onDelete}
      />
      <DocumentDropZone add={add} onBrowse={onBrowse} empty={false} />
      <DocumentPreviewDialog document={opened} onClose={() => setOpenedId(null)} />
    </>
  );
}

/**
 * The top bar and the page column, whatever the state of the knowledge base. With `onDropFiles`,
 * files can be dropped anywhere under the top bar.
 */
function KnowledgeFrame({
  actions,
  onDropFiles,
  children,
}: {
  actions?: ReactNode;
  onDropFiles?: (files: File[]) => void;
  children: ReactNode;
}) {
  const t = useTranslations("knowledge");
  const column = (
    <div className="mx-auto flex w-full max-w-275 flex-col gap-5 px-8 pt-7 pb-24">{children}</div>
  );
  return (
    <div className="flex flex-1 flex-col">
      <div className="sticky top-0 z-10 flex h-13 items-center gap-2 border-b bg-card px-6">
        <span className="font-medium">{t("breadcrumb")}</span>
        <div className="flex-1" />
        {actions}
      </div>
      <FileDropArea
        onFiles={(files) => onDropFiles?.(files)}
        disabled={!onDropFiles}
        className="flex flex-1 flex-col"
      >
        {column}
      </FileDropArea>
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

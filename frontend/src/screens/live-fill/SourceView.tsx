"use client";

import { useTranslations } from "next-intl";
import { SourceViewer } from "@/features/document-preview";
import { documentFileUrl, type KnowledgeDocument } from "@/features/knowledge-base";
import { fieldSources, type QueueField } from "@/features/review-queue";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { formatDate } from "@/shared/utils/date";

/**
 * The Source tab of Live fill: the document a field's value was read from, opened where the
 * quote is, the quote highlighted. Several sources: one at a time, chosen above the document.
 */
export function SourceView({
  field,
  sourceIndex,
  onSourceIndex,
  documents,
}: {
  field: QueueField | undefined;
  sourceIndex: number;
  onSourceIndex: (index: number) => void;
  /** The company documents (undefined while they load). */
  documents: KnowledgeDocument[] | undefined;
}) {
  const t = useTranslations("source");
  if (!field) {
    return <Message title={t("noFieldTitle")}>{t("noField")}</Message>;
  }
  const sources = fieldSources(field);
  if (sources.length === 0) {
    return (
      <Message title={t("noSourceTitle")}>
        {field.type === "missing" && documents
          ? t("noSourceSearched", { count: documents.length, label: field.label })
          : t("noSource")}
      </Message>
    );
  }
  const index = Math.min(sourceIndex, sources.length - 1);
  const { citation, candidate } = sources[index];
  const document = documents?.find((entry) => entry.id === citation.document_id);
  const date = candidate.source_date?.date;

  return (
    <div className="flex flex-col gap-3">
      {sources.length > 1 && (
        <div role="group" aria-label={t("sources")} className="flex flex-wrap gap-1.5">
          {sources.map((source, other) => (
            <Button
              key={other}
              size="xs"
              variant="outline"
              aria-pressed={other === index}
              onClick={() => onSourceIndex(other)}
              className={cn(other === index && "border-foreground bg-muted")}
            >
              {source.candidate.value}
            </Button>
          ))}
        </div>
      )}
      <header className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {document && (
          <span className="rounded-[3px] bg-foreground px-1 py-px font-mono text-[9px] font-semibold text-background uppercase">
            {document.file_format}
          </span>
        )}
        <h2 className="font-semibold text-foreground">{citation.document_name}</h2>
        {citation.page !== null && <span>{t("page", { number: citation.page + 1 })}</span>}
        {date && <span>{t("dated", { date: formatDate(date) })}</span>}
        <span className="flex-1" />
        <span className="rounded-md bg-foreground px-2 py-0.5 text-[11px] text-background">
          {t("usedFor", { label: field.label })}
        </span>
      </header>
      <SourceBody citation={citation} document={document} documentsLoaded={!!documents} />
    </div>
  );
}

function SourceBody({
  citation,
  document,
  documentsLoaded,
}: {
  citation: ReturnType<typeof fieldSources>[number]["citation"];
  document: KnowledgeDocument | undefined;
  documentsLoaded: boolean;
}) {
  const t = useTranslations("source");
  const focus = { page: citation.page, quote: citation.quote };
  if (document) {
    return (
      <SourceViewer
        key={document.id}
        fileUrl={documentFileUrl(document.id)}
        fileFormat={document.file_format}
        label={document.name}
        focus={focus}
      />
    );
  }
  // The tender details, or a document since removed from the company knowledge: the quote only.
  return (
    <figure className="flex flex-col gap-2 rounded-lg bg-card p-5 text-sm shadow-sm ring-1 ring-border">
      <blockquote>
        <mark className="rounded-[2px] bg-yellow-200 px-0.5">{citation.quote}</mark>
      </blockquote>
      {citation.document_id !== null && documentsLoaded && (
        <figcaption className="text-xs text-muted-foreground">{t("documentRemoved")}</figcaption>
      )}
    </figure>
  );
}

function Message({ title, children }: { title: string; children: string }) {
  return (
    <div className="mx-auto mt-20 flex max-w-md flex-col gap-1 text-center text-sm text-muted-foreground">
      <h2 className="font-semibold text-foreground">{title}</h2>
      <p>{children}</p>
    </div>
  );
}

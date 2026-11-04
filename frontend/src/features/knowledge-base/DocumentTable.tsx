import { useTranslations } from "next-intl";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Card } from "@/shared/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { formatDay } from "@/shared/utils/date";
import { documentFileUrl, type KnowledgeDocument } from "./knowledge-base.api";

const STATUS_VARIANT = {
  processing: "info",
  indexed: "success",
  error: "destructive",
} as const satisfies Record<KnowledgeDocument["status"], string>;

/** The company documents the AI answers from, with their indexing status. */
export function DocumentTable({ documents }: { documents: KnowledgeDocument[] }) {
  const t = useTranslations("knowledge");
  return (
    <Card className="gap-0 py-0">
      <Table aria-label={t("documents")}>
        <TableHeader>
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            <TableHead className="w-12" />
            <TableHead>{t("column.document")}</TableHead>
            <TableHead className="w-28">{t("column.pages")}</TableHead>
            <TableHead className="w-32">{t("column.added")}</TableHead>
            <TableHead className="w-28">{t("column.status")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((document) => (
            <DocumentRow key={document.id} document={document} />
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function DocumentRow({ document }: { document: KnowledgeDocument }) {
  const t = useTranslations("knowledge");
  return (
    <TableRow aria-label={document.name}>
      <TableCell className="pl-4">
        <FormatTile format={document.file_format} />
      </TableCell>
      <TableCell className="min-w-0 whitespace-normal">
        <a
          href={documentFileUrl(document.id)}
          target="_blank"
          rel="noreferrer"
          className="font-medium hover:underline"
        >
          {document.name}
        </a>
        <div className="truncate text-xs text-muted-foreground">{document.file_name}</div>
        {document.error && <p className="mt-1 text-xs text-destructive">{document.error}</p>}
      </TableCell>
      <TableCell className="text-muted-foreground">
        {document.pages === null ? t("noPages") : t("pages", { count: document.pages })}
      </TableCell>
      <TableCell className="text-muted-foreground">{formatDay(document.created_at)}</TableCell>
      <TableCell>
        <Badge variant={STATUS_VARIANT[document.status]}>{t(`status.${document.status}`)}</Badge>
      </TableCell>
    </TableRow>
  );
}

function FormatTile({ format }: { format: KnowledgeDocument["file_format"] }) {
  return (
    <div
      className={cn(
        "grid h-8 w-7 place-items-center rounded-[5px] font-mono text-[8.5px] font-bold text-primary-foreground",
        format === "pdf" ? "bg-destructive" : "bg-primary",
      )}
    >
      {format.toUpperCase()}
    </div>
  );
}

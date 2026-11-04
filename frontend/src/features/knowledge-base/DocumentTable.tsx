import { useState } from "react";
import { DownloadIcon, LoaderCircleIcon, Trash2Icon } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/shared/lib/utils";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/shared/ui/alert-dialog";
import { Badge } from "@/shared/ui/badge";
import { Button, buttonVariants } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { formatDay } from "@/shared/utils/date";
import { documentFileUrl, type KnowledgeDocument } from "./knowledge-base.api";

const STATUS_VARIANT = {
  processing: "info",
  indexed: "success",
  error: "destructive",
} as const satisfies Record<KnowledgeDocument["status"], string>;

/**
 * The company documents the AI answers from, with their indexing status. Clicking a document's
 * name asks to preview it (`onOpen`); each row also has its download link and a delete button,
 * which asks for confirmation before calling `onDelete`.
 */
export function DocumentTable({
  documents,
  onOpen,
  onDelete,
}: {
  documents: KnowledgeDocument[];
  onOpen: (document: KnowledgeDocument) => void;
  onDelete: (document: KnowledgeDocument) => void;
}) {
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
            <TableHead className="w-22" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((document) => (
            <DocumentRow
              key={document.id}
              document={document}
              onOpen={() => onOpen(document)}
              onDelete={() => onDelete(document)}
            />
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function DocumentRow({
  document,
  onOpen,
  onDelete,
}: {
  document: KnowledgeDocument;
  onOpen: () => void;
  onDelete: () => void;
}) {
  const t = useTranslations("knowledge");
  return (
    <TableRow aria-label={document.name}>
      <TableCell className="pl-4">
        <FormatTile format={document.file_format} />
      </TableCell>
      <TableCell className="min-w-0 whitespace-normal">
        <button
          type="button"
          onClick={onOpen}
          aria-label={t("open", { name: document.name })}
          className="cursor-pointer text-left font-medium hover:underline"
        >
          {document.name}
        </button>
        <div className="truncate text-xs text-muted-foreground">{document.file_name}</div>
        {document.error && <p className="mt-1 text-xs text-destructive">{document.error}</p>}
        {document.status === "processing" && (
          <p className="mt-1 text-xs text-muted-foreground">{t("reading")}</p>
        )}
      </TableCell>
      <TableCell className="text-muted-foreground">
        {document.pages === null ? t("noPages") : t("pages", { count: document.pages })}
      </TableCell>
      <TableCell className="text-muted-foreground">{formatDay(document.created_at)}</TableCell>
      <TableCell>
        <Badge variant={STATUS_VARIANT[document.status]}>
          {document.status === "processing" && (
            <LoaderCircleIcon data-icon="inline-start" className="animate-spin" aria-hidden />
          )}
          {t(`status.${document.status}`)}
        </Badge>
      </TableCell>
      <TableCell className="pr-4">
        <div className="flex justify-end gap-0.5">
          <a
            href={documentFileUrl(document.id)}
            download
            aria-label={t("downloadDocument", { name: document.name })}
            title={t("download")}
            className={buttonVariants({ variant: "ghost", size: "icon-sm" })}
          >
            <DownloadIcon />
          </a>
          <DeleteButton document={document} onConfirm={onDelete} />
        </div>
      </TableCell>
    </TableRow>
  );
}

/** Deleting is irreversible: the trash button asks first. */
function DeleteButton({
  document,
  onConfirm,
}: {
  document: KnowledgeDocument;
  onConfirm: () => void;
}) {
  const t = useTranslations("knowledge");
  const [open, setOpen] = useState(false);
  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t("deleteDocument", { name: document.name })}
            title={t("deleteConfirm")}
            className="text-muted-foreground hover:text-destructive"
          />
        }
      >
        <Trash2Icon />
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("deleteTitle", { name: document.name })}</AlertDialogTitle>
          <AlertDialogDescription>{t("deleteDescription")}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={() => {
              // The action button does not close the dialog by itself.
              setOpen(false);
              onConfirm();
            }}
          >
            {t("deleteConfirm")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
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

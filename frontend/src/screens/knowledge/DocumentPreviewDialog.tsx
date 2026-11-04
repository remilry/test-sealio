"use client";

import { DownloadIcon, FileTextIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { PdfViewer } from "@/features/document-preview";
import { documentFileUrl, type KnowledgeDocument } from "@/features/knowledge-base";
import { EmptyState } from "@/shared/components/LoadStates";
import { buttonVariants } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";

/** A company document opened from the list: read it in place, or download it. */
export function DocumentPreviewDialog({
  document,
  onClose,
}: {
  document: KnowledgeDocument | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={document !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="flex max-h-[92dvh] flex-col gap-4 sm:max-w-3xl">
        {document && <PreviewContent document={document} />}
      </DialogContent>
    </Dialog>
  );
}

function PreviewContent({ document }: { document: KnowledgeDocument }) {
  const t = useTranslations("knowledge");
  const fileUrl = documentFileUrl(document.id);
  return (
    <>
      <DialogHeader className="flex-row items-start justify-between gap-4 pr-8">
        <div className="flex min-w-0 flex-col gap-1.5">
          <DialogTitle>{document.name}</DialogTitle>
          <DialogDescription className="truncate">{document.file_name}</DialogDescription>
        </div>
        <a href={fileUrl} download className={buttonVariants({ variant: "outline", size: "sm" })}>
          <DownloadIcon data-icon="inline-start" />
          {t("download")}
        </a>
      </DialogHeader>
      <div className="-mx-4 -mb-4 min-h-0 flex-1 overflow-y-auto bg-muted/40 p-4">
        <DocumentBody document={document} fileUrl={fileUrl} />
      </div>
    </>
  );
}

function DocumentBody({ document, fileUrl }: { document: KnowledgeDocument; fileUrl: string }) {
  const t = useTranslations("knowledge");
  // Word documents: preview planned with step 7 (docx-preview).
  if (document.file_format !== "pdf") {
    return (
      <EmptyState icon={<FileTextIcon />} level={2} title={t("previewDocxTitle")}>
        {t("previewDocx")}
      </EmptyState>
    );
  }
  return <PdfViewer fileUrl={fileUrl} label={document.name} />;
}

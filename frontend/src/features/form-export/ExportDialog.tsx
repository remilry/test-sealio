"use client";

import type { ReactNode } from "react";
import { CircleCheckIcon, DownloadIcon, PenLineIcon, TriangleAlertIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { LoadError } from "@/shared/components/LoadStates";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button, buttonVariants } from "@/shared/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/ui/dialog";
import { Skeleton } from "@/shared/ui/skeleton";
import { exportedFileUrl, type ExportSummary } from "./form-export.api";
import { useExportSummary } from "./form-export.queries";

/**
 * Export (docs/USER_FLOW.md §3.5), over the form being filled: the last check, the download in the
 * original format, and what is left to do by hand. Closing it goes back to the review.
 */
export function ExportDialog({
  formId,
  formTitle,
  fileFormat,
  savePending,
}: {
  formId: number;
  formTitle: string;
  fileFormat: string;
  /** A value is being saved: the summary waits for it, so it counts every answer. */
  savePending: boolean;
}) {
  const t = useTranslations("export");
  const format = fileFormat.toUpperCase();
  return (
    <Dialog>
      <DialogTrigger render={<Button />}>
        <DownloadIcon data-icon="inline-start" />
        {t("open", { format })}
      </DialogTrigger>
      <DialogContent className="gap-5 sm:max-w-lg">
        <ExportContent
          formId={formId}
          formTitle={formTitle}
          format={format}
          savePending={savePending}
        />
      </DialogContent>
    </Dialog>
  );
}

/** Mounted only while the dialog is open, so the summary is fetched again at every opening. */
function ExportContent({
  formId,
  formTitle,
  format,
  savePending,
}: {
  formId: number;
  formTitle: string;
  format: string;
  savePending: boolean;
}) {
  const t = useTranslations("export");
  const summary = useExportSummary(formId, { enabled: !savePending });

  if (summary.error) {
    return (
      <ExportPending formTitle={formTitle} format={format}>
        <LoadError title={t("loadError")} onRetry={() => void summary.refetch()} />
      </ExportPending>
    );
  }
  if (!summary.data) {
    return (
      <ExportPending formTitle={formTitle} format={format}>
        <div aria-label={t("preparing")} className="flex flex-col gap-3">
          <Skeleton className="h-5 w-1/2" />
          <Skeleton className="h-20 w-full" />
        </div>
      </ExportPending>
    );
  }
  return (
    <ExportReady formId={formId} formTitle={formTitle} format={format} summary={summary.data} />
  );
}

/** The dialog before the summary is there: a neutral header, then the loading or error state. */
function ExportPending({
  formTitle,
  format,
  children,
}: {
  formTitle: string;
  format: string;
  children: ReactNode;
}) {
  const t = useTranslations("export");
  return (
    <>
      <DialogHeader>
        <DialogTitle>{t("title", { format })}</DialogTitle>
        <DialogDescription>{formTitle}</DialogDescription>
      </DialogHeader>
      {children}
    </>
  );
}

function ExportReady({
  formId,
  formTitle,
  format,
  summary,
}: {
  formId: number;
  formTitle: string;
  format: string;
  summary: ExportSummary;
}) {
  const t = useTranslations("export");
  const empty = summary.empty_fields.length;

  return (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-lg font-semibold">
          <ReadinessTitle emptyCount={empty} />
        </DialogTitle>
        <DialogDescription>
          {t("filledSummary", { formTitle, filled: summary.filled, fillable: summary.fillable })}
        </DialogDescription>
      </DialogHeader>

      {empty > 0 && (
        <Alert className="border-warning/40 bg-warning/5">
          <TriangleAlertIcon className="text-warning" />
          <AlertTitle>{t("emptyWarning", { count: empty })}</AlertTitle>
          <AlertDescription>
            <ul aria-label={t("emptyFields")} className="list-inside list-disc">
              {summary.empty_fields.map((field) => (
                <li key={field.id}>{field.label}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {summary.sign_by_hand.length > 0 && (
        <section aria-labelledby="before-you-submit" className="flex flex-col gap-1.5">
          <h3 id="before-you-submit" className="text-sm font-semibold">
            {t("beforeSubmit")}
          </h3>
          <ul className="flex flex-col gap-1 text-sm">
            {summary.sign_by_hand.map((field) => (
              <li key={field.id} className="flex items-center gap-2">
                <PenLineIcon className="size-4 text-muted-foreground" aria-hidden />
                {t("signByHand", { label: field.label })}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="-mx-4 -mb-4 flex flex-col gap-3 rounded-b-xl border-t bg-muted/50 p-4">
        <p className="text-xs text-muted-foreground">{t("layoutPreserved")}</p>
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <DialogClose render={<Button variant="outline" />}>{t("backToReview")}</DialogClose>
          <a href={exportedFileUrl(formId)} download className={buttonVariants()}>
            <DownloadIcon data-icon="inline-start" />
            {t("download", { format })}
          </a>
        </div>
      </div>
    </>
  );
}

function ReadinessTitle({ emptyCount }: { emptyCount: number }) {
  const t = useTranslations("export");
  if (emptyCount > 0) return t("stillEmpty", { count: emptyCount });
  return (
    <>
      <CircleCheckIcon className="size-5 text-success" aria-hidden />
      {t("ready")}
    </>
  );
}

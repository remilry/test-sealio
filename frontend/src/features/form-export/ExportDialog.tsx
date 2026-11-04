"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleCheckIcon, DownloadIcon, PenLineIcon, TriangleAlertIcon } from "lucide-react";
import { messages } from "@/shared/lib/messages";
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/shared/ui/alert";
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
import { exportedFileUrl, exportQueries, type ExportSummary } from "./api";

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;

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
  const format = fileFormat.toUpperCase();
  return (
    <Dialog>
      <DialogTrigger render={<Button />}>
        <DownloadIcon data-icon="inline-start" />
        Export {format}
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
  const summary = useQuery({ ...exportQueries.summary(formId), enabled: !savePending });

  if (summary.data) {
    return (
      <ExportReady formId={formId} formTitle={formTitle} format={format} summary={summary.data} />
    );
  }
  return (
    <>
      <DialogHeader>
        <DialogTitle>Export {format}</DialogTitle>
        <DialogDescription>{formTitle}</DialogDescription>
      </DialogHeader>
      {summary.error ? (
        <Alert variant="destructive">
          <AlertTitle>We couldn&apos;t prepare the export.</AlertTitle>
          <AlertDescription>{messages.retryLater}</AlertDescription>
          <AlertAction>
            <Button variant="outline" size="sm" onClick={() => void summary.refetch()}>
              Try again
            </Button>
          </AlertAction>
        </Alert>
      ) : (
        <div aria-label="Preparing the export" className="flex flex-col gap-3">
          <Skeleton className="h-5 w-1/2" />
          <Skeleton className="h-20 w-full" />
        </div>
      )}
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
  const empty = summary.empty_fields.length;

  return (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-lg font-semibold">
          {empty === 0 ? (
            <>
              <CircleCheckIcon className="size-5 text-success" aria-hidden />
              Ready to submit
            </>
          ) : (
            `${plural(empty, "field")} still empty`
          )}
        </DialogTitle>
        <DialogDescription>
          {formTitle} · {summary.filled} of {summary.fillable} fields filled
        </DialogDescription>
      </DialogHeader>

      {empty > 0 && (
        <Alert className="border-warning/40 bg-warning/5">
          <TriangleAlertIcon className="text-warning" />
          <AlertTitle>
            {plural(empty, "field")} still empty — {empty === 1 ? "it" : "they"} will be exported
            blank
          </AlertTitle>
          <AlertDescription>
            <ul aria-label="Empty fields" className="list-inside list-disc">
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
            Before you submit
          </h3>
          <ul className="flex flex-col gap-1 text-sm">
            {summary.sign_by_hand.map((field) => (
              <li key={field.id} className="flex items-center gap-2">
                <PenLineIcon className="size-4 text-muted-foreground" aria-hidden />
                Sign by hand: {field.label}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="-mx-4 -mb-4 flex flex-col gap-3 rounded-b-xl border-t bg-muted/50 p-4">
        <p className="text-xs text-muted-foreground">
          Buyer&apos;s original layout preserved · answers written into the existing fields
        </p>
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <DialogClose render={<Button variant="outline" />}>Back to review</DialogClose>
          <a href={exportedFileUrl(formId)} download className={buttonVariants()}>
            <DownloadIcon data-icon="inline-start" />
            Download {format}
          </a>
        </div>
      </div>
    </>
  );
}

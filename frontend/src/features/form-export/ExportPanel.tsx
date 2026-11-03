import Link from "next/link";
import { CircleCheckIcon, DownloadIcon, PenLineIcon, TriangleAlertIcon } from "lucide-react";
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { buttonVariants } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { exportedFileUrl, type ExportSummary } from "./api";

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;

/** What will be exported, the warnings, the download in the original format, and what is left to do by hand. */
export function ExportPanel({
  formId,
  formTitle,
  summary,
  reviewHref,
}: {
  formId: number;
  formTitle: string;
  summary: ExportSummary;
  reviewHref: string;
}) {
  const empty = summary.empty_fields.length;
  const format = summary.file_format.toUpperCase();

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1.5">
        <p className="text-sm text-muted-foreground">{formTitle}</p>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          {empty === 0 ? (
            <>
              <CircleCheckIcon className="size-6 text-success" aria-hidden />
              Ready to submit
            </>
          ) : (
            `${plural(empty, "field")} still empty`
          )}
        </h1>
        <p className="text-sm text-muted-foreground">
          {summary.filled} of {summary.fillable} fields filled
        </p>
      </header>

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
          <AlertAction>
            <Link href={reviewHref} className={buttonVariants({ variant: "outline", size: "sm" })}>
              Back to review
            </Link>
          </AlertAction>
        </Alert>
      )}

      <Card className="flex flex-col gap-3 px-5 py-5">
        <a
          href={exportedFileUrl(formId)}
          download
          className={buttonVariants({ size: "lg", className: "w-fit px-4" })}
        >
          <DownloadIcon data-icon="inline-start" />
          Download {format}
        </a>
        <p className="text-xs text-muted-foreground">
          Buyer&apos;s original layout preserved · answers written into the existing fields
        </p>
      </Card>

      {summary.sign_by_hand.length > 0 && (
        <section aria-labelledby="before-you-submit" className="flex flex-col gap-2">
          <h2 id="before-you-submit" className="text-[15px] font-semibold">
            Before you submit
          </h2>
          <ul className="flex flex-col gap-1.5 text-sm">
            {summary.sign_by_hand.map((field) => (
              <li key={field.id} className="flex items-center gap-2">
                <PenLineIcon className="size-4 text-muted-foreground" aria-hidden />
                Sign by hand: {field.label}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

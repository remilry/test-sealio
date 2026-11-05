"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { ClockIcon, LandmarkIcon, LibraryIcon, TriangleAlertIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { ApiError } from "@/shared/api";
import { routes } from "@/shared/lib/routes";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/ui/dialog";
import { useStartFill } from "./fill-session.queries";

type SetupForm = {
  id: number;
  title: string;
  file_name: string;
  field_counts: { fields: number; yes_no: number; signatures: number } | null;
  estimated_fill_seconds: number | null;
};

/**
 * The Setup step: the form (with `preview`, its pages), what the automatic fill answers from and
 * how long it takes, then Start. `documentCount` is undefined while the company knowledge is
 * unknown (loading or failed): then neither its count nor the empty warning is shown.
 */
export function SetupDialog({
  form,
  documentCount,
  preview,
  onStarted,
}: {
  form: SetupForm;
  documentCount: number | undefined;
  /** The form's pages, shown beside the details (rendered by the caller: another feature). */
  preview?: ReactNode;
  onStarted: () => void;
}) {
  const t = useTranslations("autoFill");
  const [open, setOpen] = useState(false);
  const start = useStartFill(form.id);

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) start.reset();
  };
  const handleStart = () =>
    start.mutate(undefined, {
      onSuccess: onStarted,
      // 409: already filled, or a fill is already running (a colleague, another tab). Either way
      // Live fill is the right place: review the answers or follow the run.
      onError: (error) => {
        if (error instanceof ApiError && error.status === 409) onStarted();
      },
    });

  // Any failure but a 409 (handled above), a network error included, shows in the dialog.
  const error = start.error;
  const failure = error && !(error instanceof ApiError && error.status === 409) ? error : null;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={<Button />}>{t("trigger")}</DialogTrigger>
      <DialogContent
        className={cn("gap-0 overflow-hidden p-0", preview ? "sm:max-w-4xl" : "sm:max-w-xl")}
      >
        <div className={cn("grid", preview && "md:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]")}>
          {preview && (
            <div className="hidden max-h-[70vh] overflow-y-auto border-r bg-muted/60 p-4 md:block">
              {preview}
            </div>
          )}
          <div className="flex flex-col gap-5 p-6">
            {/* Clear of the close button (top right of the dialog). */}
            <DialogHeader className="pr-8">
              <DialogTitle className="text-lg leading-snug font-semibold">
                {t("title", { formTitle: form.title })}
              </DialogTitle>
              <DialogDescription className="leading-relaxed">{t("intro")}</DialogDescription>
            </DialogHeader>
            <FileCard form={form} />
            <Sources documentCount={documentCount} />
            {failure && <Failure error={failure} />}
          </div>
        </div>
        <div className="flex items-center gap-2 border-t bg-muted/40 px-6 py-4">
          <span className="flex flex-1 items-center gap-1.5 text-xs text-muted-foreground">
            {form.estimated_fill_seconds !== null && (
              <>
                <ClockIcon className="size-3.5" />
                {t("duration", { seconds: form.estimated_fill_seconds })}
              </>
            )}
          </span>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            {t("cancel")}
          </Button>
          <Button onClick={handleStart} disabled={start.isPending}>
            {t("start")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** The form's file: its format, its name and what was detected in it. */
function FileCard({ form }: { form: SetupForm }) {
  const tCommon = useTranslations("common");
  const extension = form.file_name.split(".").pop()?.toUpperCase() ?? "";
  return (
    <div className="flex items-center gap-3 rounded-lg border bg-muted/30 px-3.5 py-3">
      <span
        aria-hidden
        className={cn(
          "grid h-9 w-7.5 flex-none place-items-center rounded-[5px] font-mono text-[8px] font-bold text-white",
          extension === "PDF" ? "bg-destructive" : "bg-primary",
        )}
      >
        {extension}
      </span>
      <div className="min-w-0">
        <p className="truncate font-medium">{form.file_name}</p>
        {form.field_counts && (
          <p className="mt-0.5 text-xs text-muted-foreground">
            {tCommon("fieldCounts", {
              fields: form.field_counts.fields,
              yesNo: form.field_counts.yes_no,
              signatures: form.field_counts.signatures,
            })}
          </p>
        )}
      </div>
    </div>
  );
}

/** Where the answers come from: the company knowledge (counted once known) and the tender. */
function Sources({ documentCount }: { documentCount: number | undefined }) {
  const t = useTranslations("autoFill");
  return (
    <section aria-labelledby="setup-sources" className="flex flex-col gap-2">
      <h3
        id="setup-sources"
        className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase"
      >
        {t("sources")}
      </h3>
      <ul className="flex flex-col gap-1.5">
        <Source
          icon={<LibraryIcon />}
          label={t("companyKnowledge")}
          detail={
            documentCount === undefined ? undefined : t("documentCount", { count: documentCount })
          }
        >
          {documentCount === 0 && (
            <p className="mt-1.5 flex items-start gap-1.5 text-xs text-warning">
              <TriangleAlertIcon className="mt-px size-3.5 flex-none" />
              <span>
                {t("knowledgeEmpty")}{" "}
                <Link href={routes.knowledge} className="font-medium text-primary hover:underline">
                  {t("addDocuments")}
                </Link>
              </span>
            </p>
          )}
        </Source>
        <Source icon={<LandmarkIcon />} label={t("tenderDetails")} detail={t("tenderDetailsSub")} />
      </ul>
    </section>
  );
}

function Source({
  icon,
  label,
  detail,
  children,
}: {
  icon: ReactNode;
  label: string;
  detail?: string;
  children?: ReactNode;
}) {
  return (
    <li className="flex items-start gap-3 rounded-lg border px-3 py-2.5">
      <span className="grid size-7 flex-none place-items-center rounded-md bg-primary/10 text-primary [&_svg]:size-4">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{label}</p>
        {detail && <p className="text-xs text-muted-foreground">{detail}</p>}
        {children}
      </div>
    </li>
  );
}

function Failure({ error }: { error: Error }) {
  const t = useTranslations("autoFill");
  const tCommon = useTranslations("common");
  if (!(error instanceof ApiError) || error.status !== 503) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {tCommon("retryLater")}
      </p>
    );
  }
  return (
    <div role="alert" className="flex flex-col gap-0.5 text-sm">
      <p className="font-medium text-destructive">{t("unavailable")}</p>
      <p className="text-muted-foreground">{error.message}</p>
    </div>
  );
}

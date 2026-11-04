"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { ApiError } from "@/shared/api";
import { routes } from "@/shared/lib/routes";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/ui/dialog";
import { useStartFill } from "./fill-session.queries";

type SetupForm = {
  id: number;
  title: string;
  file_name: string;
  field_counts: { fields: number } | null;
  estimated_fill_seconds: number | null;
};

/** The Setup step: what the automatic fill uses and how long it takes, then Start. */
export function SetupDialog({
  form,
  documentCount,
  onStarted,
}: {
  form: SetupForm;
  documentCount: number;
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

  const error = start.error;
  const failure = error instanceof ApiError && error.status !== 409 ? error : null;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={<Button />}>{t("trigger")}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("title", { formTitle: form.title })}</DialogTitle>
          <DialogDescription>{form.file_name}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3 text-sm">
          {form.field_counts && <p>{t("fieldsDetected", { count: form.field_counts.fields })}</p>}
          <ul aria-label={t("sources")} className="flex list-disc flex-col gap-1 pl-5">
            <li>{t("companyKnowledge", { count: documentCount })}</li>
            <li>{t("tenderDetails")}</li>
          </ul>
          {documentCount === 0 && (
            <p className="text-muted-foreground">
              {t("knowledgeEmpty")}{" "}
              <Link href={routes.knowledge} className="font-medium text-primary hover:underline">
                {t("addDocuments")}
              </Link>
            </p>
          )}
          {form.estimated_fill_seconds !== null && (
            <p className="text-muted-foreground">
              {t("duration", { seconds: form.estimated_fill_seconds })}
            </p>
          )}
          {failure && <Failure error={failure} />}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            {t("cancel")}
          </Button>
          <Button onClick={handleStart} disabled={start.isPending}>
            {t("start")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Failure({ error }: { error: ApiError }) {
  const t = useTranslations("autoFill");
  const tCommon = useTranslations("common");
  if (error.status !== 503) return <p role="alert">{tCommon("retryLater")}</p>;
  return (
    <div role="alert" className="flex flex-col gap-0.5">
      <p className="font-medium">{t("unavailable")}</p>
      <p className="text-muted-foreground">{error.message}</p>
    </div>
  );
}

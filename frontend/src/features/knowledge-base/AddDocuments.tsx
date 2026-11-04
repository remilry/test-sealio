"use client";

import { useRef } from "react";
import { PlusIcon, TriangleAlertIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { ApiError } from "@/shared/api";
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { ACCEPTED_FILES } from "./knowledge-base.api";
import { useAddDocuments } from "./knowledge-base.queries";

/**
 * "Add documents": picks PDF or Word files and sends them. Renders the button and, under it in the
 * page, why the last files were refused (`AddDocumentsError`), both driven by `useAddDocuments`.
 */
export function AddDocumentsButton({ add }: { add: ReturnType<typeof useAddDocuments> }) {
  const t = useTranslations("knowledge");
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPTED_FILES}
        aria-label={t("chooseFiles")}
        className="sr-only"
        tabIndex={-1}
        onChange={(event) => {
          const files = Array.from(event.currentTarget.files ?? []);
          // Cleared so choosing the same file again still triggers a change.
          event.currentTarget.value = "";
          if (files.length > 0) add.mutate(files);
        }}
      />
      <Button size="sm" disabled={add.isPending} onClick={() => input.current?.click()}>
        <PlusIcon data-icon="inline-start" />
        {add.isPending ? t("adding") : t("addDocuments")}
      </Button>
    </>
  );
}

/** Why the files could not be added: the back's reason when it refused them, written for users. */
export function AddDocumentsError({ add }: { add: ReturnType<typeof useAddDocuments> }) {
  const t = useTranslations("knowledge");
  if (!add.error) return null;
  return (
    <Alert variant="destructive">
      <TriangleAlertIcon />
      <AlertTitle>{t("addFailed")}</AlertTitle>
      <AlertDescription>{refusal(add.error) ?? t("addFailedRetry")}</AlertDescription>
      <AlertAction>
        <Button variant="outline" size="sm" onClick={() => add.reset()}>
          {t("dismiss")}
        </Button>
      </AlertAction>
    </Alert>
  );
}

function refusal(error: Error): string | null {
  return error instanceof ApiError && error.status === 422 ? error.message : null;
}

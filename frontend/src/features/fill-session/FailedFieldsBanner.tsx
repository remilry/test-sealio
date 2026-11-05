"use client";

import { CircleAlertIcon, RotateCwIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { useRetryFill } from "./fill-session.queries";

/**
 * Above the fields, when a fill could not answer some of them (their model call kept failing):
 * how many, and a Retry that fills only those again. `unavailable`: nothing could be answered.
 */
export function FailedFieldsBanner({
  formId,
  count,
  unavailable,
}: {
  formId: number;
  count: number;
  unavailable: boolean;
}) {
  const t = useTranslations("liveFill");
  const retry = useRetryFill(formId);
  return (
    <Alert variant={unavailable ? "destructive" : "default"}>
      <CircleAlertIcon />
      <AlertTitle>{unavailable ? t("unavailableTitle") : t("failedTitle", { count })}</AlertTitle>
      <AlertDescription>
        {unavailable && t("failedTitle", { count })}
        {unavailable && " · "}
        {t("failedDescription")}
      </AlertDescription>
      <AlertAction>
        <Button
          variant="outline"
          size="sm"
          disabled={retry.isPending}
          onClick={() => retry.mutate()}
        >
          <RotateCwIcon />
          {retry.isPending ? t("retrying") : t("retry")}
        </Button>
      </AlertAction>
    </Alert>
  );
}

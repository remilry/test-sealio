"use client";

import { CircleAlertIcon, RotateCwIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { ApiError } from "@/shared/api";
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
  const tCommon = useTranslations("common");
  const retry = useRetryFill(formId);
  const failure = retry.error ? whyNot(retry.error, tCommon("retryLater")) : null;
  return (
    <Alert variant={unavailable ? "destructive" : "default"}>
      <CircleAlertIcon />
      <AlertTitle>{unavailable ? t("unavailableTitle") : t("failedTitle", { count })}</AlertTitle>
      <AlertDescription>
        {unavailable && t("failedTitle", { count })}
        {unavailable && " · "}
        {t("failedDescription")}
        {failure && <p className="font-medium text-destructive">{failure}</p>}
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

/** Why Retry did not start: the back's refusals (409, 503) are worded for the user, anything
 * else (network, unexpected) is said in plain words. */
function whyNot(error: Error, fallback: string): string {
  if (error instanceof ApiError && (error.status === 409 || error.status === 503)) {
    return error.message;
  }
  return fallback;
}

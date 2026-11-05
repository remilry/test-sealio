"use client";

import { TriangleAlertIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/shared/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/shared/ui/empty";

/** A screen that crashed: said in plain words (nothing technical), with a way to try again. */
export function ErrorPage({ onRetry }: { onRetry: () => void }) {
  const t = useTranslations("common");
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <TriangleAlertIcon />
        </EmptyMedia>
        <EmptyTitle role="heading" aria-level={1}>
          {t("errorTitle")}
        </EmptyTitle>
        <EmptyDescription>{t("retryLater")}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button variant="outline" onClick={onRetry}>
          {t("tryAgain")}
        </Button>
      </EmptyContent>
    </Empty>
  );
}

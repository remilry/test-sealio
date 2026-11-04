"use client";

import { useTranslations } from "next-intl";
import { Button } from "@/shared/ui/button";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/shared/ui/alert-dialog";
import { useDiscardFill } from "./fill-session.queries";

/** Confirms, then deletes every answer of the form (the user's too). */
export function DiscardFillDialog({
  formId,
  formTitle,
  open,
  onOpenChange,
  onDiscarded,
}: {
  formId: number;
  formTitle: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDiscarded?: () => void;
}) {
  const t = useTranslations("discardFill");
  const discard = useDiscardFill(formId);

  const handleOpenChange = (next: boolean) => {
    onOpenChange(next);
    if (!next) discard.reset();
  };
  const handleDiscard = () =>
    discard.mutate(undefined, {
      onSuccess: () => {
        handleOpenChange(false);
        onDiscarded?.();
      },
    });

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("title", { formTitle })}</AlertDialogTitle>
          <AlertDialogDescription>{t("description")}</AlertDialogDescription>
        </AlertDialogHeader>
        {discard.isError && (
          <p role="alert" className="text-sm text-destructive">
            {t("failed")}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
          <Button variant="destructive" onClick={handleDiscard} disabled={discard.isPending}>
            {t("discard")}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

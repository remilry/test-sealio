"use client";

import { useState } from "react";
import { RotateCcwIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { routes } from "@/shared/lib/routes";
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
import { useResetDemo } from "./dev-tools.queries";

/**
 * Floating button (bottom right) that puts the demo back to its start: no company document,
 * every form "not started". Development only: the caller renders it in `next dev` only.
 */
export function DevResetButton() {
  const t = useTranslations("devTools");
  const [open, setOpen] = useState(false);
  const reset = useResetDemo();

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) reset.reset();
  };
  // A full reload: running streams and screen state go too, the demo starts on Company knowledge.
  const handleReset = () =>
    reset.mutate(undefined, { onSuccess: () => window.location.assign(routes.knowledge) });

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className="fixed right-4 bottom-4 z-50 shadow-md"
        onClick={() => setOpen(true)}
      >
        <RotateCcwIcon />
        {t("reset")}
      </Button>
      <AlertDialog open={open} onOpenChange={handleOpenChange}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("title")}</AlertDialogTitle>
            <AlertDialogDescription>{t("description")}</AlertDialogDescription>
          </AlertDialogHeader>
          {reset.isError && (
            <p role="alert" className="text-sm text-destructive">
              {t("failed")}
            </p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
            <Button variant="destructive" onClick={handleReset} disabled={reset.isPending}>
              {t("confirm")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { MoreHorizontalIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { DiscardFillDialog, SetupDialog } from "@/features/fill-session";
import type { FormSummary } from "@/features/tender";
import { routes } from "@/shared/lib/routes";
import { Button, buttonVariants } from "@/shared/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/ui/dropdown-menu";

/**
 * The action of a form that can be filled: "Auto-fill" (Setup) while untouched; once started (or
 * while a fill runs) "Continue review" and a menu to discard the answers. No re-run on a started form.
 */
export function FormAction({ form, documentCount }: { form: FormSummary; documentCount: number }) {
  const t = useTranslations("forms");
  const router = useRouter();
  const [discarding, setDiscarding] = useState(false);

  if (form.status === "not_started" && !form.filling) {
    return (
      <SetupDialog
        form={form}
        documentCount={documentCount}
        onStarted={() => router.push(routes.fillForm(form.id))}
      />
    );
  }
  return (
    <div className="flex items-center gap-1.5">
      <Link href={routes.fillForm(form.id)} className={buttonVariants({ variant: "outline" })}>
        {t("continueReview")}
      </Link>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={<Button variant="ghost" size="icon" aria-label={t("moreActions")} />}
        >
          <MoreHorizontalIcon />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-auto">
          <DropdownMenuItem onClick={() => setDiscarding(true)}>
            {t("discardAnswers")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <DiscardFillDialog
        formId={form.id}
        formTitle={form.title}
        open={discarding}
        onOpenChange={setDiscarding}
      />
    </div>
  );
}

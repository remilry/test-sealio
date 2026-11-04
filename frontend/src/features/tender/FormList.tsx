import type { ReactNode } from "react";
import { CheckIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import type { FormSummary } from "./tender.api";

const STATUS_VARIANT = {
  not_started: "secondary",
  in_review: "info",
  ready: "success",
} as const satisfies Record<FormSummary["status"], string>;

/** The buyer forms of a tender, one row per form, in the tender's order. */
export function FormList({
  forms,
  renderAction,
}: {
  forms: FormSummary[];
  /** The action of a form that can be filled (the screen composes it: features don't import each other). */
  renderAction: (form: FormSummary) => ReactNode;
}) {
  const t = useTranslations("forms");
  return (
    <section aria-labelledby="forms-to-complete" className="flex flex-col gap-2.5">
      <div className="flex items-baseline justify-between gap-4">
        <h2 id="forms-to-complete" className="text-[15px] font-semibold">
          {t("title")}
        </h2>
        <p className="text-xs text-muted-foreground">{t("hint")}</p>
      </div>
      <Card className="gap-0 py-0">
        <ul aria-label={t("title")} className="divide-y">
          {forms.map((form) => (
            <FormRow key={form.id} form={form} renderAction={renderAction} />
          ))}
        </ul>
      </Card>
    </section>
  );
}

function FormRow({
  form,
  renderAction,
}: {
  form: FormSummary;
  renderAction: (form: FormSummary) => ReactNode;
}) {
  const t = useTranslations("forms");
  return (
    <li
      aria-label={form.title}
      className="grid grid-cols-[36px_minmax(0,1fr)_auto_auto] items-center gap-4 px-4.5 py-4"
    >
      <FormatTile format={form.file_format} />
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold">{form.title}</div>
        <div className="mt-0.5 truncate text-xs text-muted-foreground">
          {form.field_counts ? <FieldCounts counts={form.field_counts} /> : form.file_name}
        </div>
      </div>
      <Badge variant={STATUS_VARIANT[form.status]}>
        {form.status === "ready" && <CheckIcon data-icon="inline-start" />}
        {t(`status.${form.status}`)}
      </Badge>
      <div className="flex justify-end">
        {form.field_counts ? (
          renderAction(form)
        ) : (
          // This file format cannot be parsed yet: nothing to fill.
          <Button disabled title={t("formatNotSupported")}>
            {t("autoFill")}
          </Button>
        )}
      </div>
    </li>
  );
}

/** "10 fields detected · 2 Yes/No declarations · 1 signature" */
function FieldCounts({ counts }: { counts: NonNullable<FormSummary["field_counts"]> }) {
  const t = useTranslations("forms");
  return [
    t("fieldsDetected", { count: counts.fields }),
    counts.yes_no > 0 && t("yesNoDeclarations", { count: counts.yes_no }),
    counts.signatures > 0 && t("signatures", { count: counts.signatures }),
  ]
    .filter(Boolean)
    .join(" · ");
}

function FormatTile({ format }: { format: FormSummary["file_format"] }) {
  return (
    <div
      className={cn(
        "grid h-10 w-[34px] place-items-center rounded-md font-mono text-[8.5px] font-bold text-primary-foreground",
        format === "pdf" ? "bg-destructive" : "bg-primary",
      )}
    >
      {format.toUpperCase()}
    </div>
  );
}

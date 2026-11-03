import { CheckIcon, SparklesIcon } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import type { FormSummary } from "./api";

const STATUS = {
  not_started: { label: "Not started", variant: "secondary" },
  in_review: { label: "In review", variant: "info" },
  ready: { label: "Ready", variant: "success" },
} as const satisfies Record<FormSummary["status"], { label: string; variant: string }>;

/** The buyer forms of a tender, one row per form, in the tender's order. */
export function FormList({ forms }: { forms: FormSummary[] }) {
  return (
    <section aria-labelledby="forms-to-complete" className="flex flex-col gap-2.5">
      <div className="flex items-baseline justify-between gap-4">
        <h2 id="forms-to-complete" className="text-[15px] font-semibold">
          Forms to complete
        </h2>
        <p className="text-xs text-muted-foreground">
          Buyer templates · filled in place, layout preserved
        </p>
      </div>
      <Card className="gap-0 py-0">
        <ul aria-label="Forms to complete" className="divide-y">
          {forms.map((form) => (
            <FormRow key={form.id} form={form} />
          ))}
        </ul>
      </Card>
    </section>
  );
}

function FormRow({ form }: { form: FormSummary }) {
  const status = STATUS[form.status];
  return (
    <li
      aria-label={form.title}
      className="grid grid-cols-[36px_minmax(0,1fr)_auto_auto] items-center gap-4 px-4.5 py-4"
    >
      <FormatTile format={form.file_format} />
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold">{form.title}</div>
        <div className="mt-0.5 truncate text-xs text-muted-foreground">{form.file_name}</div>
      </div>
      <Badge variant={status.variant}>
        {form.status === "ready" && <CheckIcon data-icon="inline-start" />}
        {status.label}
      </Badge>
      <div className="flex justify-end">
        {form.status === "not_started" && (
          // Opens the Setup step once it exists (next slice).
          <Button disabled title="Available in the next step">
            <SparklesIcon data-icon="inline-start" />
            Fill with AI
          </Button>
        )}
      </div>
    </li>
  );
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

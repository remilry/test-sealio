"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { ArrowLeftIcon, FileXIcon } from "lucide-react";
import { DocumentPreview, type PreviewZone, type ZoneTone } from "@/features/document-preview";
import {
  originalFileUrl,
  SaveIndicator,
  useFillState,
  useFormDetail,
  useSaveAnswer,
  type FillState,
  type FormDetail,
} from "@/features/fill-session";
import { ExportDialog } from "@/features/form-export";
import { FieldList, type FocusRequest, type QueueField } from "@/features/review-queue";
import { useTender } from "@/features/tender";
import { isNotFound } from "@/shared/api";
import { EmptyState, LoadError } from "@/shared/components/LoadStates";
import { useHandleKeyDown } from "@/shared/lib/hooks/useHandleKeyDown";
import { routes } from "@/shared/lib/routes";
import { buttonVariants } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";

/**
 * Live fill (docs/USER_FLOW.md §3.4): the fields on the left, the original form on the right,
 * kept in sync. Step 4.5: the user types every value; the AI fills them from step 5.
 */
export function LiveFillScreen({ formId }: { formId: number }) {
  const form = useFormDetail(formId);
  const fill = useFillState(formId);

  if (form.isPending || fill.isPending) {
    return (
      <Frame>
        <LoadingState />
      </Frame>
    );
  }
  if (form.isError || fill.isError) {
    return (
      <FormLoadFailed
        error={form.error ?? fill.error}
        onRetry={() => {
          void form.refetch();
          void fill.refetch();
        }}
      />
    );
  }
  return <FillWorkspace form={form.data} fill={fill.data} />;
}

function FormLoadFailed({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  if (isNotFound(error)) {
    return (
      <Frame>
        <EmptyState title="Form not found">It may have been withdrawn by the buyer.</EmptyState>
      </Frame>
    );
  }
  return (
    <Frame>
      <div className="mx-auto w-full max-w-xl p-8">
        <LoadError title="We couldn't load this form." onRetry={onRetry} />
      </div>
    </Frame>
  );
}

function FillWorkspace({ form, fill }: { form: FormDetail; fill: FillState }) {
  const { data: tender } = useTender(form.tender_id);
  // Values the back refused: kept in their input (and on the document) until saved.
  const [unsaved, setUnsaved] = useState<ReadonlyMap<number, string>>(new Map());
  const save = useSaveAnswer(form.id, {
    onFailed: ({ fieldId, value }) => {
      setUnsaved((previous) => withEntry(previous, fieldId, value ?? ""));
      setDraft(fieldId, value ?? "");
    },
  });

  const answers = new Map(fill.answers.map((answer) => [answer.field_id, answer]));
  // Text being typed, not saved yet: shown on the document at every keystroke.
  const [drafts, setDrafts] = useState<ReadonlyMap<number, string>>(new Map());
  const setDraft = (fieldId: number, text: string | null) =>
    setDrafts((previous) => withEntry(previous, fieldId, text));
  const fields: QueueField[] = form.fields.map((field) => ({
    id: field.id,
    label: field.label,
    fillable: field.kind !== "signature",
    value: answers.get(field.id)?.value ?? null,
    unsaved: unsaved.get(field.id) ?? null,
    enteredAt: answers.get(field.id)?.resolved_at ?? null,
  }));
  const zones: PreviewZone[] = form.fields.map((field, index) => {
    const value = (drafts.get(field.id) ?? fields[index].value ?? "").trim() || null;
    return {
      id: field.id,
      label: field.label,
      page: field.locator.page,
      box: field.locator.box,
      fontSize: field.locator.font_size,
      placeholders: field.locator.erase,
      value,
      tone: zoneTone(fields[index], value),
    };
  });
  const fillable = fields.filter((field) => field.fillable);

  const [chosenId, setChosenId] = useState<number | null>(null);
  const [focusRequest, setFocusRequest] = useState<FocusRequest | null>(null);
  // Until the user picks one, the first field without a value is selected.
  const selectedId =
    chosenId ?? (fillable.find((field) => !field.value) ?? fillable[0] ?? fields[0])?.id ?? null;

  const focusField = (fieldId: number) => {
    setChosenId(fieldId);
    if (fields.find((field) => field.id === fieldId)?.fillable) {
      setFocusRequest((previous) => ({ fieldId, at: (previous?.at ?? 0) + 1 }));
    }
  };
  const moveSelection = (step: 1 | -1) => {
    const index = fields.findIndex((field) => field.id === selectedId);
    const next = fields[Math.min(Math.max(index + step, 0), fields.length - 1)];
    if (next) setChosenId(next.id);
  };
  const focusNextFillable = (fieldId: number) => {
    const index = fields.findIndex((field) => field.id === fieldId);
    const next = fields.slice(index + 1).find((field) => field.fillable);
    if (next) focusField(next.id);
  };

  useHandleKeyDown({
    ArrowDown: () => moveSelection(1),
    j: () => moveSelection(1),
    ArrowUp: () => moveSelection(-1),
    k: () => moveSelection(-1),
    Enter: () => selectedId !== null && focusField(selectedId),
  });

  if (!form.field_counts) {
    return (
      <Frame form={form} tenderTitle={tender?.title}>
        <EmptyState icon={<FileXIcon />} level={2} title="This form can't be filled yet">
          Only PDF forms can be filled for now. You can still download the original from the tender.
        </EmptyState>
      </Frame>
    );
  }

  const { counts } = fill;
  return (
    <Frame
      form={form}
      tenderTitle={tender?.title}
      status={
        <>
          <SaveIndicator formId={form.id} />
          <span className="text-xs whitespace-nowrap text-muted-foreground">
            {counts.filled} / {counts.fillable} filled · {counts.empty} empty
          </span>
          <ExportDialog
            formId={form.id}
            formTitle={form.title}
            fileFormat={form.file_format}
            savePending={save.isPending}
          />
        </>
      }
    >
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(320px,420px)_minmax(0,1fr)]">
        <div className="flex min-h-0 flex-col gap-4 overflow-y-auto border-r bg-card/50 p-5">
          <header className="flex flex-col gap-1">
            <h2 className="text-[15px] font-semibold">
              {counts.empty === 0
                ? "All fields are filled"
                : `${counts.empty} ${counts.empty === 1 ? "field" : "fields"} to fill`}
            </h2>
            <p className="text-xs text-muted-foreground">
              Type each answer: it is saved as you go and shown on the form. Press Enter to move to
              the next field.
            </p>
          </header>
          <FieldList
            fields={fields}
            selectedId={selectedId}
            focusRequest={focusRequest}
            onSelect={setChosenId}
            onSave={(fieldId, value) => {
              // The saved answer takes over from the draft (and comes back if the save fails).
              setDraft(fieldId, null);
              setUnsaved((previous) => withEntry(previous, fieldId, null));
              save.mutate({ fieldId, value });
            }}
            onNext={focusNextFillable}
            onDraft={setDraft}
          />
        </div>
        <div className="min-h-0 overflow-y-auto bg-muted/40 p-6">
          <div className="mx-auto max-w-[760px]">
            <DocumentPreview
              fileUrl={originalFileUrl(form.id)}
              pages={form.pages}
              zones={zones}
              selectedId={selectedId}
              onSelect={focusField}
            />
          </div>
        </div>
      </div>
    </Frame>
  );
}

/** Full-screen layout (no sidebar) with the top bar. */
function Frame({
  form,
  tenderTitle,
  status,
  children,
}: {
  form?: FormDetail;
  tenderTitle?: string;
  status?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex h-dvh flex-col">
      <div className="flex h-13 flex-none items-center gap-3 border-b bg-card px-4">
        {form && (
          <Link
            href={routes.tender(form.tender_id)}
            aria-label="Back to the tender"
            className={buttonVariants({ variant: "outline", size: "icon-sm" })}
          >
            <ArrowLeftIcon />
          </Link>
        )}
        <span className="grid size-5.5 flex-none place-items-center rounded-md bg-foreground text-[11px] font-bold text-background">
          F
        </span>
        <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-sm">
          {tenderTitle && (
            <>
              <span className="truncate text-muted-foreground">{tenderTitle}</span>
              <span className="text-border">/</span>
            </>
          )}
          {form && <h1 className="truncate font-medium">{form.title}</h1>}
        </nav>
        <div className="flex-1" />
        {status}
      </div>
      {children}
    </div>
  );
}

function LoadingState() {
  return (
    <div aria-label="Loading form" className="grid flex-1 grid-cols-[420px_1fr] gap-6 p-5">
      <div className="flex flex-col gap-2">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-20 w-full" />
        ))}
      </div>
      <Skeleton className="aspect-[595/842] w-full max-w-[760px]" />
    </div>
  );
}

/** A copy of the map with the entry set, or removed when `text` is null. */
function withEntry(map: ReadonlyMap<number, string>, id: number, text: string | null) {
  const next = new Map(map);
  if (text === null) next.delete(id);
  else next.set(id, text);
  return next;
}

/** How a field shows on the document: to sign by hand, entered, or still empty. */
function zoneTone(field: QueueField, value: string | null): ZoneTone {
  if (!field.fillable) return "signature";
  return value ? "entered" : "empty";
}

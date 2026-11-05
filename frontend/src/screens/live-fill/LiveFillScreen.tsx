"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeftIcon, CircleAlertIcon, FileXIcon, MoreHorizontalIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { DocumentPreview, type PreviewZone, type ZoneTone } from "@/features/document-preview";
import {
  DiscardFillDialog,
  FillProgress,
  originalFileUrl,
  SaveIndicator,
  useFillRun,
  useFillState,
  useFormDetail,
  useSaveAnswer,
  type Answer,
  type FillRun,
  type FillState,
  type FormDetail,
} from "@/features/fill-session";
import { ExportDialog } from "@/features/form-export";
import { useKnowledgeBase } from "@/features/knowledge-base";
import {
  FieldList,
  groupFields,
  nextOpen,
  type FocusRequest,
  type QueueField,
} from "@/features/review-queue";
import { useTender } from "@/features/tender";
import { isNotFound } from "@/shared/api";
import { EmptyState, LoadError } from "@/shared/components/LoadStates";
import { useHandleKeyDown } from "@/shared/lib/hooks/useHandleKeyDown";
import { routes } from "@/shared/lib/routes";
import { Alert, AlertTitle } from "@/shared/ui/alert";
import { Button, buttonVariants } from "@/shared/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/ui/dropdown-menu";
import { Skeleton } from "@/shared/ui/skeleton";

/**
 * Live fill (docs/USER_FLOW.md §3.4): the fields on the left, the original form on the right,
 * kept in sync. While the form fills itself, both follow the run field by field.
 */
export function LiveFillScreen({ formId }: { formId: number }) {
  // Once discarded, nothing of the form is read or followed any more (its data is gone): the
  // screen waits for the navigation to the tender.
  const [discarded, setDiscarded] = useState(false);
  if (discarded) {
    return (
      <Frame>
        <LoadingState />
      </Frame>
    );
  }
  return <LiveFill formId={formId} onDiscarded={() => setDiscarded(true)} />;
}

function LiveFill({ formId, onDiscarded }: { formId: number; onDiscarded: () => void }) {
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
  return <FillWorkspace form={form.data} fill={fill.data} onDiscarded={onDiscarded} />;
}

function FormLoadFailed({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const t = useTranslations("liveFill");
  const tCommon = useTranslations("common");
  if (isNotFound(error)) {
    return (
      <Frame>
        <EmptyState title={t("notFound")}>{tCommon("withdrawnByBuyer")}</EmptyState>
      </Frame>
    );
  }
  return (
    <Frame>
      <div className="mx-auto w-full max-w-xl p-8">
        <LoadError title={t("loadError")} onRetry={onRetry} />
      </div>
    </Frame>
  );
}

function FillWorkspace({
  form,
  fill,
  onDiscarded,
}: {
  form: FormDetail;
  fill: FillState;
  onDiscarded: () => void;
}) {
  const t = useTranslations("liveFill");
  const { data: tender } = useTender(form.tender_id);
  const { data: knowledge } = useKnowledgeBase();
  const router = useRouter();
  const [discarding, setDiscarding] = useState(false);
  // Also right after Setup: starting the fill refetches the answers, whose run is then running.
  const run = useFillRun(form.id, { follow: fill.ai_run?.status === "running" });
  const filling = fill.ai_run?.status === "running" && run.outcome === null;
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
  const fields: QueueField[] = form.fields.map((field) => {
    const answer = answers.get(field.id);
    return {
      id: field.id,
      label: field.label,
      fillable: field.kind !== "signature",
      yesNo: field.kind === "yes_no",
      value: answer?.value ?? null,
      unsaved: unsaved.get(field.id) ?? null,
      enteredAt: answer?.resolved_by === "user" ? answer.resolved_at : null,
      state: fieldState(run, field.id),
      // What the user saved is theirs: the fill does not write over it.
      writing: answer?.resolved_by === "user" ? null : (run.writing.get(field.id) ?? null),
      type: answer?.type ?? null,
      resolvedBy: answer?.resolved_by ?? null,
      proposedValue: answer?.proposed_value ?? null,
      candidates: answer?.candidates ?? [],
      userOnlyReason: answer?.user_only_reason ?? null,
    };
  });
  const zones: PreviewZone[] = form.fields.map((field, index) => {
    const draft = drafts.get(field.id);
    const value = (draft ?? fields[index].value ?? "").trim() || null;
    const writing = value === null ? fields[index].writing : null;
    return {
      id: field.id,
      label: field.label,
      value: value ?? writing,
      tone: writing
        ? "writing"
        : zoneTone(fields[index], value, draft === undefined ? answers.get(field.id) : undefined),
      place: placeOf(field.locator),
    };
  });
  const fillable = fields.filter((field) => field.fillable);

  // Once the fill is over, the fields are reviewed group by group: doubts, no value, automatic.
  const grouped = !filling;
  const queue = grouped ? queueOrder(fields) : fields;
  const [chosenId, setChosenId] = useState<number | null>(null);
  const [focusRequest, setFocusRequest] = useState<FocusRequest | null>(null);
  // Until the user picks one, the first open field is selected (once the fill is over: meanwhile
  // the selection would jump at every answer).
  const firstOpen = nextOpen(fields, -1) ?? (fillable[0] ?? fields[0])?.id;
  const selectedId = chosenId ?? (filling ? null : (firstOpen ?? null));

  const focusField = (fieldId: number) => {
    setChosenId(fieldId);
    if (fields.find((field) => field.id === fieldId)?.fillable) {
      setFocusRequest((previous) => ({ fieldId, at: (previous?.at ?? 0) + 1 }));
    }
  };
  const moveSelection = (step: 1 | -1) => {
    const index = queue.findIndex((field) => field.id === selectedId);
    const next = queue[Math.min(Math.max(index + step, 0), queue.length - 1)];
    if (next) setChosenId(next.id);
  };
  // After a field: the next open one in the review queue, or the next one in the form while the
  // form fills.
  const focusNext = (fieldId: number) => {
    if (grouped) {
      const next = nextOpen(fields, fieldId);
      if (next !== null) focusField(next);
      return;
    }
    const index = fields.findIndex((field) => field.id === fieldId);
    const next = fields.slice(index + 1).find((field) => field.fillable);
    if (next) focusField(next.id);
  };
  const saveField = (fieldId: number, value: string | null) => {
    // The saved answer takes over from the draft (and comes back if the save fails).
    setDraft(fieldId, null);
    setUnsaved((previous) => withEntry(previous, fieldId, null));
    save.mutate({ fieldId, value });
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
        <EmptyState icon={<FileXIcon />} level={2} title={t("cannotFillTitle")}>
          {t("cannotFillDescription")}
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
          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button variant="ghost" size="icon-sm" aria-label={t("moreActions")} />}
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
            onDiscarded={() => {
              onDiscarded();
              router.push(routes.tender(form.tender_id));
            }}
          />
          <SaveIndicator formId={form.id} />
          <span className="text-xs whitespace-nowrap text-muted-foreground">
            {t("progress", counts)}
          </span>
          <ExportDialog
            formId={form.id}
            formTitle={form.title}
            fileFormat={form.file_format}
            savePending={save.isPending}
            filling={filling}
            onReview={focusField}
          />
        </>
      }
    >
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(320px,420px)_minmax(0,1fr)]">
        <div className="flex min-h-0 flex-col gap-4 overflow-y-auto border-r bg-card/50 p-5">
          <FillHeader
            run={run}
            filling={filling}
            openCount={counts.open}
            estimatedSeconds={form.estimated_fill_seconds}
            startedAt={fill.ai_run?.started_at ?? null}
          />
          <FieldList
            fields={fields}
            grouped={grouped}
            selectedId={selectedId}
            focusRequest={focusRequest}
            context={
              knowledge && {
                companyName: knowledge.company_name,
                documentCount: knowledge.documents.length,
              }
            }
            onSelect={setChosenId}
            onSave={saveField}
            onSettle={(fieldId, value) => {
              saveField(fieldId, value);
              focusNext(fieldId);
            }}
            onNext={focusNext}
            onDraft={setDraft}
          />
        </div>
        <div className="min-h-0 overflow-y-auto bg-muted/40 p-6">
          <div className="mx-auto max-w-[760px]">
            <DocumentPreview
              fileUrl={originalFileUrl(form.id)}
              fileFormat={form.file_format}
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

/** The top of the left column: the fill under way, or what is left to fill (after its outcome). */
function FillHeader({
  run,
  filling,
  openCount,
  estimatedSeconds,
  startedAt,
}: {
  run: FillRun;
  filling: boolean;
  /** Fields nobody settled yet that are empty or have a doubt. */
  openCount: number;
  estimatedSeconds: number | null;
  startedAt: string | null;
}) {
  const t = useTranslations("liveFill");
  if (filling && startedAt) {
    return (
      <header className="flex flex-col gap-2">
        <h2 className="text-[15px] font-semibold">{t("filling")}</h2>
        <p className="flex justify-between gap-2 text-xs text-muted-foreground">
          <span>{t(`phase.${run.phase ?? "reading_form"}`)}</span>
          {run.toAnswer !== null && (
            <span className="tabular-nums">
              {t("answeredOfTotal", { answered: run.answered.size, total: run.toAnswer })}
            </span>
          )}
        </p>
        <FillProgress run={run} estimatedSeconds={estimatedSeconds} startedAt={startedAt} />
      </header>
    );
  }
  const { outcome } = run;
  return (
    <header className="flex flex-col gap-1">
      {outcome?.kind === "error" && (
        <Alert variant="destructive" className="mb-2">
          <CircleAlertIcon />
          <AlertTitle>{t("fillStopped", { message: outcome.message })}</AlertTitle>
        </Alert>
      )}
      {outcome?.kind === "done" && (
        <p className="text-xs font-medium text-success">
          {t("fillDone", {
            filled: outcome.filled,
            fillable: outcome.fillable,
            seconds: outcome.seconds,
          })}
        </p>
      )}
      <h2 className="text-[15px] font-semibold">
        {openCount === 0 ? t("allReviewed") : t("needALook", { count: openCount })}
      </h2>
      <p className="text-xs text-muted-foreground">{t("instructions")}</p>
    </header>
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
  const t = useTranslations("liveFill");
  const tCommon = useTranslations("common");
  return (
    <div className="flex h-dvh flex-col">
      <div className="flex h-13 flex-none items-center gap-3 border-b bg-card px-4">
        {form && (
          <Link
            href={routes.tender(form.tender_id)}
            aria-label={t("backToTender")}
            className={buttonVariants({ variant: "outline", size: "icon-sm" })}
          >
            <ArrowLeftIcon />
          </Link>
        )}
        <span className="grid size-5.5 flex-none place-items-center rounded-md bg-foreground text-[11px] font-bold text-background">
          {tCommon("appName").charAt(0)}
        </span>
        <nav aria-label={t("breadcrumb")} className="flex min-w-0 items-center gap-2 text-sm">
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
  const t = useTranslations("liveFill");
  return (
    <div aria-label={t("loading")} className="grid flex-1 grid-cols-[420px_1fr] gap-6 p-5">
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

/** The fields as the review queue lists them: groups in order, then signatures. */
function queueOrder(fields: QueueField[]): QueueField[] {
  const { groups, signatures } = groupFields(fields);
  return [...groups.flatMap((group) => group.fields), ...signatures];
}

/** Where the preview draws a field, from the parser's locator. */
function placeOf(locator: FormDetail["fields"][number]["locator"]): PreviewZone["place"] {
  if (locator.format === "docx") return { format: "docx", locator };
  return {
    format: "pdf",
    page: locator.page,
    box: locator.box,
    fontSize: locator.font_size,
    placeholders: locator.erase,
  };
}

function fieldState(run: FillRun, fieldId: number): QueueField["state"] {
  if (run.answered.has(fieldId)) return "answered";
  if (run.searching.has(fieldId)) return "searching";
  return "pending";
}

/**
 * How a field shows on the document. `answer` is the saved answer, or undefined while the user is
 * typing (what is typed is theirs).
 */
function zoneTone(field: QueueField, value: string | null, answer: Answer | undefined): ZoneTone {
  if (!field.fillable) return "signature";
  // A value saved while the field is searched is the user's: the fill will not replace it.
  if (value && answer?.resolved_by === "user") return "entered";
  if (field.state === "searching") return "searching";
  if (!value) return "empty";
  if (!answer || answer.resolved_by === "user") return "entered";
  if (["conflict", "outdated", "manual", "unsure"].includes(answer.type ?? "")) {
    return "toCheck";
  }
  return "auto";
}

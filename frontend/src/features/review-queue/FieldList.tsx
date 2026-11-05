"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { CheckIcon, PenLineIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/shared/lib/utils";
import type { Schema } from "@/shared/api";
import { Button, buttonVariants } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { formatDate, formatTime } from "@/shared/utils/date";
import { groupFields, isOpen, reviewGroup, settledAs, type ReviewGroup } from "./review";

/** A field as the list shows it: what the user sees and edits, nothing of the file layout. */
export type QueueField = {
  id: number;
  label: string;
  /** Signatures and stamps are shown but never filled. */
  fillable: boolean;
  /** A Yes/No declaration is answered with two choices instead of text. */
  yesNo: boolean;
  value: string | null;
  /** What the user typed but could not be saved: kept in the input so they can try again. */
  unsaved: string | null;
  /** When the user entered the value (ISO timestamp); null when it was filled automatically. */
  enteredAt: string | null;
  /** Where the automatic fill is for this field: not reached yet, being searched, answered. */
  state: "pending" | "searching" | "answered";
  /** The value the automatic fill is writing, not verified yet (null when none). */
  writing: string | null;
  /** How sure the answer is (null for the user's own value or no answer). */
  type: Schema<"AnswerOut">["type"];
  resolvedBy: "ai" | "user" | null;
  /** What the automatic fill wrote, kept when the user changes it (null when it never answered). */
  proposedValue: string | null;
  /** The values found and the quotes supporting them; the selected one is the first. */
  candidates: Schema<"Candidate">[];
  /** Why only the user can fill this field. */
  userOnlyReason: string | null;
};

/** What the status lines name: the bidder and how many documents were searched (when known). */
export type FieldContext = { companyName: string; documentCount: number };

/** Ask the list to move the keyboard focus to a field's input (changes on every request). */
export type FocusRequest = { fieldId: number; at: number };

type CardHandlers = {
  onSelect: (fieldId: number) => void;
  onSave: (fieldId: number, value: string | null) => void;
  /** The user settles a field: keeps or chooses a value, or leaves it empty on purpose. */
  onSettle: (fieldId: number, value: string | null) => void;
  onNext: (fieldId: number) => void;
  onDraft: (fieldId: number, text: string) => void;
};

/**
 * The fields of the form, each with its input. A value is saved when the user leaves the input
 * or presses Enter (which also moves on). Every keystroke is reported through `onDraft`, so the
 * document can show the text while it is typed.
 *
 * Grouped (once the form is not filling any more), the review queue: doubts to check first, then
 * fields without a value, then the automatic answers, collapsed; filters on top.
 */
export function FieldList({
  fields,
  grouped,
  selectedId,
  focusRequest,
  context,
  ...handlers
}: {
  context: FieldContext | undefined;
  fields: QueueField[];
  grouped: boolean;
  selectedId: number | null;
  focusRequest: FocusRequest | null;
} & CardHandlers) {
  const t = useTranslations("fieldList");
  const inputs = useRef(new Map<number, HTMLInputElement>());
  const [filter, setFilter] = useState<ReviewGroup | null>(null);
  const [showAutomatic, setShowAutomatic] = useState(false);

  useEffect(() => {
    if (focusRequest) inputs.current.get(focusRequest.fieldId)?.focus();
  }, [focusRequest]);

  const card = (field: QueueField) => (
    <FieldCard
      key={field.id}
      field={field}
      selected={field.id === selectedId}
      context={context}
      inputRef={(input) => {
        if (input) inputs.current.set(field.id, input);
        else inputs.current.delete(field.id);
      }}
      focusInput={() => {
        const input = inputs.current.get(field.id);
        input?.focus();
        input?.select();
      }}
      {...handlers}
    />
  );

  if (!grouped) {
    return (
      <ol aria-label={t("label")} className="flex flex-col gap-2">
        {fields.map(card)}
      </ol>
    );
  }

  const { groups, signatures } = groupFields(fields);
  const selected = fields.find((field) => field.id === selectedId);
  // The automatic answers open when one of them is selected (from the document, for instance).
  const automaticOpen =
    showAutomatic || (selected !== undefined && reviewGroup(selected) === "automatic");
  const shown = groups.filter(
    ({ group, fields: inGroup }) => inGroup.length > 0 && (!filter || filter === group),
  );
  return (
    <div className="flex flex-col gap-3">
      <div role="group" aria-label={t("filter")} className="flex flex-wrap gap-1.5">
        {groups.map(({ group, fields: inGroup, open }) => (
          <Button
            key={group}
            size="xs"
            variant="outline"
            aria-pressed={filter === group}
            onClick={() => setFilter((current) => (current === group ? null : group))}
            className={cn("rounded-full", filter === group && "border-foreground bg-muted")}
          >
            <span aria-hidden className={cn("size-2 rounded-full", GROUP_DOT[group])} />
            {t(`group.${group}.pill`, { count: group === "automatic" ? inGroup.length : open })}
          </Button>
        ))}
      </div>
      <ol aria-label={t("label")} className="flex flex-col gap-4">
        {shown.map(({ group, fields: inGroup }) => (
          <GroupSection
            key={group}
            title={t(`group.${group}.title`)}
            action={
              group === "automatic" && (
                <Button variant="ghost" size="xs" onClick={() => setShowAutomatic(!automaticOpen)}>
                  {automaticOpen ? t("hide") : t("show")}
                </Button>
              )
            }
          >
            {group === "automatic" && !automaticOpen ? (
              <li className="rounded-lg border border-dashed px-3.5 py-2.5 text-xs text-muted-foreground">
                {t("automaticCollapsed", { count: inGroup.length })}
              </li>
            ) : (
              inGroup.map(card)
            )}
          </GroupSection>
        ))}
        {signatures.length > 0 && !filter && (
          <GroupSection title={t("group.signature.title")}>{signatures.map(card)}</GroupSection>
        )}
      </ol>
    </div>
  );
}

const GROUP_DOT: Record<ReviewGroup, string> = {
  toCheck: "bg-warning",
  noValue: "bg-destructive",
  automatic: "bg-primary",
};

function GroupSection({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <li aria-label={title} className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
          {title}
        </h3>
        {action}
      </div>
      <ol aria-label={title} className="flex flex-col gap-2">
        {children}
      </ol>
    </li>
  );
}

type CardProps = {
  field: QueueField;
  selected: boolean;
  context: FieldContext | undefined;
  inputRef: (input: HTMLInputElement | null) => void;
  focusInput: () => void;
} & CardHandlers;

function FieldCard(props: CardProps) {
  const t = useTranslations("fieldList");
  const { field, selected, onSelect } = props;
  return (
    <li
      aria-label={field.label}
      aria-current={selected ? "true" : undefined}
      onClick={() => onSelect(field.id)}
      className={cn(
        "rounded-lg border bg-card px-3.5 py-3 transition-colors",
        selected && "border-primary ring-3 ring-primary/15",
      )}
    >
      {field.fillable && field.yesNo && <YesNoInput {...props} />}
      {field.fillable && !field.yesNo && <FieldInput {...props} />}
      {!field.fillable && (
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium">{field.label}</span>
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <PenLineIcon className="size-3.5" aria-hidden />
            {t("signByHand")}
          </p>
        </div>
      )}
    </li>
  );
}

function FieldInput({
  field,
  selected,
  context,
  inputRef,
  focusInput,
  onSelect,
  onSave,
  onSettle,
  onNext,
  onDraft,
}: CardProps) {
  const inputId = `field-${field.id}`;
  const input = useRef<HTMLInputElement | null>(null);
  // The last value sent (or saved), so Enter then leaving the input saves once. Back to the saved
  // value when a save fails, so the kept text is sent again.
  const lastSent = useRef(field.value ?? "");
  const shown = field.unsaved ?? field.value ?? "";
  useEffect(() => {
    // A new value (saved, trimmed by the back, or found automatically) replaces the text only if
    // the user is not typing something else: text typed and not sent yet stays.
    const element = input.current;
    if (element && element.value.trim() === lastSent.current) element.value = shown;
    lastSent.current = field.value ?? "";
  }, [shown, field.value]);
  const saveIfChanged = (element: HTMLInputElement) => {
    const value = element.value.trim();
    if (value === lastSent.current) return false;
    lastSent.current = value;
    onSave(field.id, value || null);
    return true;
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const element = event.currentTarget.elements.namedItem("value");
    const saved = element instanceof HTMLInputElement && saveIfChanged(element);
    // Enter on a value to check, left as it is: the user keeps it.
    if (!saved && field.value && isOpen(field)) onSettle(field.id, field.value);
    onNext(field.id);
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium">
        {field.label}
      </label>
      <Input
        ref={(element) => {
          input.current = element;
          inputRef(element);
        }}
        id={inputId}
        name="value"
        defaultValue={shown}
        // A value being written shows greyed in the empty input, until its answer replaces it.
        placeholder={field.writing ?? undefined}
        className={cn(field.writing && "placeholder:text-muted-foreground placeholder:italic")}
        autoComplete="off"
        onFocus={() => onSelect(field.id)}
        onChange={(event) => onDraft(field.id, event.currentTarget.value)}
        onBlur={(event) => saveIfChanged(event.currentTarget)}
      />
      <FieldStatus field={field} context={context} />
      <FieldSources field={field} expanded={selected} />
      {selected && <ReviewActions field={field} onSettle={onSettle} focusInput={focusInput} />}
    </form>
  );
}

/** A Yes/No declaration: two choices, saved at once, and a way back to no answer. */
function YesNoInput({
  field,
  selected,
  context,
  inputRef,
  focusInput,
  onSelect,
  onSave,
  onSettle,
}: CardProps) {
  const t = useTranslations("fieldList");
  const name = `field-${field.id}`;
  // Stored "yes" / "no" (any case from older answers).
  const chosen = (field.unsaved ?? field.value ?? "").toLowerCase();
  return (
    <div className="flex flex-col gap-1.5">
      <fieldset className="flex flex-col gap-1.5">
        <legend className="mb-1.5 text-sm font-medium">{field.label}</legend>
        <div className="flex items-center gap-2">
          {(["yes", "no"] as const).map((option, index) => (
            <label
              key={option}
              className={cn(
                buttonVariants({ variant: chosen === option ? "default" : "outline", size: "sm" }),
                // Positioned: the hidden radio stays inside (focusing it scrolls to the card).
                "relative has-focus-visible:ring-3 has-focus-visible:ring-ring/50",
              )}
            >
              <input
                ref={index === 0 ? inputRef : undefined}
                type="radio"
                name={name}
                value={option}
                checked={chosen === option}
                onFocus={() => onSelect(field.id)}
                onChange={() => onSave(field.id, option)}
                className="sr-only"
              />
              {t(option)}
            </label>
          ))}
          {chosen && (
            <Button variant="ghost" size="sm" onClick={() => onSave(field.id, null)}>
              {t("clearAnswer")}
            </Button>
          )}
        </div>
      </fieldset>
      <FieldStatus field={field} context={context} />
      <FieldSources field={field} expanded={selected} />
      {selected && <ReviewActions field={field} onSettle={onSettle} focusInput={focusInput} />}
    </div>
  );
}

/** What the user can do to settle the selected field, while it is still open. */
function ReviewActions({
  field,
  onSettle,
  focusInput,
}: {
  field: QueueField;
  onSettle: (fieldId: number, value: string | null) => void;
  focusInput: () => void;
}) {
  const t = useTranslations("fieldList");
  if (!isOpen(field) || field.state === "searching") return null;
  if (!field.value) {
    return (
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={() => onSettle(field.id, null)}>
          {t("leaveEmpty")}
        </Button>
      </div>
    );
  }
  if (field.type === "conflict" && field.candidates.length > 1) {
    return <ConflictChoice field={field} onSettle={onSettle} />;
  }
  return (
    <div className="flex justify-end gap-2">
      <Button variant="ghost" size="sm" onClick={focusInput}>
        {t("enterNewValue")}
      </Button>
      <Button size="sm" onClick={() => onSettle(field.id, field.value)}>
        {t("keepValue")}
      </Button>
    </div>
  );
}

/** Sources that disagree: one value each, the selected (most recent) one chosen first. */
function ConflictChoice({
  field,
  onSettle,
}: {
  field: QueueField;
  onSettle: (fieldId: number, value: string | null) => void;
}) {
  const t = useTranslations("fieldList");
  const [chosen, setChosen] = useState(field.value ?? field.candidates[0].value);
  const name = `choice-${field.id}`;
  return (
    <fieldset className="flex flex-col gap-1.5 border-t pt-2">
      <legend className="mb-1 text-xs font-medium">{t("chooseValue")}</legend>
      {field.candidates.map((candidate, index) => {
        const first = candidate.citations[0];
        return (
          <label
            key={candidate.value}
            className={cn(
              "flex cursor-pointer gap-2 rounded-md border px-2.5 py-2 text-xs",
              chosen === candidate.value && "border-primary bg-primary/5",
            )}
          >
            <input
              type="radio"
              name={name}
              value={candidate.value}
              checked={chosen === candidate.value}
              onChange={() => setChosen(candidate.value)}
              className="mt-0.5"
            />
            <span className="flex flex-col gap-0.5">
              <span className="font-medium">{candidate.value}</span>
              <span className="text-muted-foreground">
                {first && <SourceName citation={first} />}
                {candidate.source_date &&
                  t("sourceDated", { date: formatDate(candidate.source_date.date) })}
                {index === 0 && candidate.source_date && t("mostRecent")}
              </span>
            </span>
          </label>
        );
      })}
      <p className="text-xs text-muted-foreground">{t("orEnterAnother")}</p>
      <div className="flex justify-end">
        <Button size="sm" onClick={() => onSettle(field.id, chosen)}>
          {t("useThisOne")}
        </Button>
      </div>
    </fieldset>
  );
}

/** The line under the input: what the field's value is, or where its search is. */
function FieldStatus({ field, context }: { field: QueueField; context: FieldContext | undefined }) {
  const t = useTranslations("fieldList");
  if (field.unsaved !== null) {
    return <p className="text-xs text-destructive">{t("notSaved")}</p>;
  }
  // A value saved while the field is searched is the user's: the fill will not replace it.
  const settled = settledAs(field);
  if (settled && field.enteredAt) {
    return (
      <p className="flex items-center gap-1 text-xs text-muted-foreground">
        <CheckIcon className="size-3.5 text-success" aria-hidden />
        {t(SETTLED_MESSAGE[settled], { time: formatTime(field.enteredAt) })}
      </p>
    );
  }
  if (field.state === "searching") {
    return (
      <p className="animate-pulse text-xs text-primary">
        {field.writing ? t("writing") : t("searching")}
      </p>
    );
  }
  if (field.type === "manual") {
    return (
      <div className="flex flex-col gap-0.5 text-xs">
        <p className="font-medium text-warning">{t("manual")}</p>
        {field.userOnlyReason && <p className="text-muted-foreground">{field.userOnlyReason}</p>}
      </div>
    );
  }
  if (field.type === "missing" && !field.value) {
    return (
      <p className="text-xs text-muted-foreground">
        {context ? t("missing", { count: context.documentCount }) : t("missingUnknown")}
      </p>
    );
  }
  if (!field.value) {
    return <p className="text-xs text-muted-foreground">{t("empty")}</p>;
  }
  if (field.type === "conflict") {
    return (
      <p className="text-xs font-medium text-warning">
        {t("conflict", { count: field.candidates.length })}
      </p>
    );
  }
  if (field.type === "outdated") {
    const validUntil = field.candidates[0]?.valid_until?.date;
    if (validUntil) {
      return (
        <p className="text-xs font-medium text-warning">
          {t("outdated", { date: formatDate(validUntil) })}
        </p>
      );
    }
    const sourceDate = field.candidates[0]?.source_date?.date;
    if (sourceDate) {
      return (
        <p className="text-xs font-medium text-warning">
          {t("outdatedOld", { date: formatDate(sourceDate) })}
        </p>
      );
    }
  }
  if (field.type === "unsure") {
    return <p className="text-xs font-medium text-warning">{t("unsure")}</p>;
  }
  if (field.type === "declaration" && context) {
    return (
      <p className="text-xs text-muted-foreground">
        {t("declaration", { company: context.companyName })}
      </p>
    );
  }
  return <p className="text-xs text-muted-foreground">{t("filledAutomatically")}</p>;
}

const SETTLED_MESSAGE = {
  kept: "keptByYou",
  leftEmpty: "leftEmptyByYou",
  entered: "enteredByYou",
} as const;

/**
 * Where the value comes from: every source when they disagree, else the selected one. Open for
 * the selected field; the others show a count (clicking the card selects it).
 */
function FieldSources({ field, expanded }: { field: QueueField; expanded: boolean }) {
  const t = useTranslations("fieldList");
  const candidates = field.type === "conflict" ? field.candidates : field.candidates.slice(0, 1);
  const citations = candidates.flatMap((candidate) => candidate.citations);
  if (citations.length === 0) return null;
  if (!expanded) {
    return (
      <p className="text-xs text-muted-foreground">
        {t("sourceCount", { count: citations.length })}
      </p>
    );
  }
  return (
    <ul aria-label={t("sources")} className="flex flex-col gap-1.5 border-t pt-2">
      {citations.map((citation, index) => (
        <li key={index} className="text-xs">
          <p className="font-medium">
            <SourceName citation={citation} />
          </p>
          <blockquote className="text-muted-foreground">
            {t("quote", { quote: citation.quote })}
          </blockquote>
        </li>
      ))}
    </ul>
  );
}

function SourceName({ citation }: { citation: Schema<"Citation"> }) {
  const t = useTranslations("fieldList");
  if (citation.document_id === null) return t("tenderDetails");
  if (citation.page === null) return t("sourceNoPage", { document: citation.document_name });
  return t("source", { document: citation.document_name, page: citation.page + 1 });
}

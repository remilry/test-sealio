"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  ArrowLeftRightIcon,
  CheckIcon,
  CircleAlertIcon,
  LoaderCircleIcon,
  MinusIcon,
  PenLineIcon,
  UserIcon,
  type LucideIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/shared/lib/utils";
import type { Schema } from "@/shared/api";
import { Button, buttonVariants } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { formatDate, formatTime } from "@/shared/utils/date";
import {
  fieldSources,
  groupFields,
  isOpen,
  reviewGroup,
  settledAs,
  type ReviewGroup,
} from "./review";

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
  /** Show where the value comes from: the field's `index`-th source (`fieldSources`). */
  onOpenSource: (fieldId: number, index: number) => void;
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
      <div role="group" aria-label={t("filter")} className="grid grid-cols-3 gap-1.5">
        {groups.map(({ group, fields: inGroup, open }) => {
          const count = group === "automatic" ? inGroup.length : open;
          return (
            <button
              key={group}
              type="button"
              aria-pressed={filter === group}
              aria-label={t(`group.${group}.pill`, { count })}
              onClick={() => setFilter((current) => (current === group ? null : group))}
              className={cn(
                "flex flex-col gap-1.5 rounded-lg border bg-card px-2.5 py-2 text-left transition-colors hover:bg-muted/60",
                filter === group && "border-foreground bg-muted",
              )}
            >
              <span className={cn("text-lg leading-none font-semibold", GROUP_TEXT[group])}>
                {count}
              </span>
              <span className="flex items-center gap-1.5 text-[11px] whitespace-nowrap text-muted-foreground">
                <span aria-hidden className={cn("size-1.5 rounded-full", GROUP_DOT[group])} />
                {t(`group.${group}.tile`)}
              </span>
            </button>
          );
        })}
      </div>
      <ol aria-label={t("label")} className="flex flex-col gap-4">
        {shown.map(({ group, fields: inGroup, open }) => (
          <GroupSection
            key={group}
            title={t(`group.${group}.title`)}
            count={inGroup.length}
            action={
              group === "automatic" ? (
                <Button variant="ghost" size="xs" onClick={() => setShowAutomatic(!automaticOpen)}>
                  {automaticOpen ? t("hide") : t("show")}
                </Button>
              ) : (
                <span
                  className={cn(
                    "text-xs font-medium",
                    open === 0 ? "text-success" : "text-muted-foreground",
                  )}
                >
                  {open === 0 ? t("groupDone") : t("groupOpen", { count: open })}
                </span>
              )
            }
          >
            {group === "automatic" && !automaticOpen ? (
              // Opens like the Show button above it (which is the way in with the keyboard).
              <li
                onClick={() => setShowAutomatic(true)}
                className="flex cursor-pointer items-center gap-2.5 rounded-lg border bg-muted/30 px-3 py-2.5 text-xs text-muted-foreground hover:bg-muted/60"
              >
                <span
                  aria-hidden
                  className="grid size-5 flex-none place-items-center rounded-md bg-success/12 text-success"
                >
                  <CheckIcon className="size-3" />
                </span>
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

const GROUP_TEXT: Record<ReviewGroup, string> = {
  toCheck: "text-warning",
  noValue: "text-destructive",
  automatic: "text-primary",
};

const GROUP_DOT: Record<ReviewGroup, string> = {
  toCheck: "bg-warning",
  noValue: "bg-destructive",
  automatic: "bg-primary",
};

function GroupSection({
  title,
  count,
  action,
  children,
}: {
  title: string;
  /** How many fields the group holds, after its title. */
  count?: number;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <li aria-label={title} className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2 px-1">
        <div className="flex items-baseline gap-1.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          <h3>{title}</h3>
          {count !== undefined && <span aria-hidden>· {count}</span>}
        </div>
        {action}
      </div>
      <ol aria-label={title} className="flex flex-col gap-0.5">
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

/**
 * A field of the list. Selected, it opens: what its value is, its sources and what can be done
 * with it. Otherwise one line (an icon, the label, the value, a tag), still editable in place.
 */
function FieldCard(props: CardProps) {
  const t = useTranslations("fieldList");
  const { field, selected, onSelect } = props;
  const item = useRef<HTMLLIElement>(null);
  // The selected card is kept in sight (chosen on the document, or the next open one).
  useEffect(() => {
    if (selected) item.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [selected]);
  return (
    <li
      ref={item}
      aria-label={field.label}
      aria-current={selected ? "true" : undefined}
      onClick={() => onSelect(field.id)}
      className={cn(
        "rounded-lg transition-colors",
        selected
          ? "my-1 border border-primary bg-card px-3 py-3 shadow-sm ring-3 ring-primary/15"
          : "cursor-pointer px-2.5 py-2 hover:bg-muted/60",
      )}
    >
      {field.fillable && field.yesNo && <YesNoInput {...props} />}
      {field.fillable && !field.yesNo && <FieldInput {...props} />}
      {!field.fillable && (
        <div className="flex items-center gap-2.5">
          <FieldIcon field={field} />
          <div className="flex min-w-0 flex-1 flex-col gap-0.5">
            <span className="truncate text-xs text-muted-foreground">{field.label}</span>
            <p className="text-xs text-muted-foreground">{t("signByHand")}</p>
          </div>
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
  onOpenSource,
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

  const valueInput = (
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
      className={cn(
        field.writing && "placeholder:text-muted-foreground placeholder:italic",
        // On one line, the value reads as text (still editable in place).
        !selected &&
          "h-6 rounded-none border-0 bg-transparent px-0 text-sm font-medium shadow-none focus-visible:ring-0 dark:bg-transparent",
      )}
      autoComplete="off"
      onFocus={() => onSelect(field.id)}
      onChange={(event) => onDraft(field.id, event.currentTarget.value)}
      onBlur={(event) => saveIfChanged(event.currentTarget)}
    />
  );

  // One tree for both layouts, the input at the same place: opening the card on focus keeps it
  // (and what is typed in it).
  return (
    <form onSubmit={submit} className={cn("flex", selected ? "flex-col" : "items-center gap-2.5")}>
      {!selected && <FieldIcon field={field} />}
      <div className={cn("flex min-w-0 flex-1 flex-col", selected && "gap-2")}>
        <CardHeader field={field} open={selected}>
          <label
            htmlFor={inputId}
            className={cn(
              selected
                ? "text-[13px] leading-snug font-semibold"
                : "truncate text-xs text-muted-foreground",
            )}
          >
            {field.label}
          </label>
        </CardHeader>
        {selected && <FieldStatus field={field} context={context} />}
        {valueInput}
        {selected && <FieldSources field={field} expanded onOpenSource={onOpenSource} />}
        {selected && <ReviewActions field={field} onSettle={onSettle} focusInput={focusInput} />}
      </div>
      {!selected && <FieldTag field={field} />}
    </form>
  );
}

/** The top of a card: its label, and its tag once open (on one line, the tag ends the line). */
function CardHeader({
  field,
  open,
  children,
}: {
  field: QueueField;
  open: boolean;
  children: ReactNode;
}) {
  return (
    <div className="flex min-w-0 items-start justify-between gap-2.5">
      {children}
      {open && <FieldTag field={field} />}
    </div>
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
  onOpenSource,
}: CardProps) {
  const t = useTranslations("fieldList");
  const name = `field-${field.id}`;
  // Stored "yes" / "no" (any case from older answers).
  const chosen = (field.unsaved ?? field.value ?? "").toLowerCase();
  const choices = (
    <div className="flex flex-none items-center gap-1.5">
      {(["yes", "no"] as const).map((option, index) => (
        <label
          key={option}
          className={cn(
            buttonVariants({
              variant: chosen === option ? "default" : "outline",
              size: selected ? "sm" : "xs",
            }),
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
      {chosen && selected && (
        <Button variant="ghost" size="sm" onClick={() => onSave(field.id, null)}>
          {t("clearAnswer")}
        </Button>
      )}
    </div>
  );

  // One tree for both layouts, the choices at the same place (as for a text field).
  return (
    <div className={cn("flex", selected ? "flex-col gap-2" : "items-center gap-2.5")}>
      {!selected && <FieldIcon field={field} />}
      <fieldset
        aria-label={field.label}
        className={cn(
          "flex min-w-0 flex-1",
          selected ? "flex-col gap-2" : "items-center justify-between gap-2",
        )}
      >
        <CardHeader field={field} open={selected}>
          <span
            aria-hidden
            className={cn(
              selected
                ? "text-[13px] leading-snug font-semibold"
                : "truncate text-xs text-muted-foreground",
            )}
          >
            {field.label}
          </span>
        </CardHeader>
        {selected && <FieldStatus field={field} context={context} />}
        {choices}
      </fieldset>
      {selected && <FieldSources field={field} expanded onOpenSource={onOpenSource} />}
      {selected && <ReviewActions field={field} onSettle={onSettle} focusInput={focusInput} />}
      {!selected && <FieldTag field={field} />}
    </div>
  );
}

type Badge = { key: TagKey; tone: BadgeTone; values?: Record<string, number> };
type BadgeTone = "auto" | "doubt" | "missing" | "user" | "progress" | "muted" | "mine";
type TagKey =
  | "auto"
  | "declared"
  | "conflict"
  | "outdated"
  | "unsure"
  | "onlyYou"
  | "noValue"
  | "empty"
  | "searching"
  | "writing"
  | "kept"
  | "entered"
  | "leftEmpty"
  | "notSaved"
  | "signature";

/** The short word that says where a field is, and its colour (one line, open or not). */
function fieldBadge(field: QueueField): Badge {
  if (!field.fillable) return { key: "signature", tone: "muted" };
  if (field.unsaved !== null) return { key: "notSaved", tone: "missing" };
  const settled = settledAs(field);
  if (settled) return { key: settled, tone: settled === "leftEmpty" ? "muted" : "user" };
  if (field.state === "searching") {
    return { key: field.writing ? "writing" : "searching", tone: "progress" };
  }
  if (field.resolvedBy === null && field.value) return { key: "entered", tone: "user" };
  switch (field.type) {
    case "conflict":
      return { key: "conflict", tone: "doubt", values: { count: field.candidates.length } };
    case "outdated":
      return { key: "outdated", tone: "doubt" };
    case "unsure":
      return { key: "unsure", tone: "doubt" };
    case "manual":
      return { key: "onlyYou", tone: "mine" };
    case "auto":
      return field.value ? { key: "auto", tone: "auto" } : { key: "noValue", tone: "missing" };
    case "declaration":
      return field.value ? { key: "declared", tone: "auto" } : { key: "noValue", tone: "missing" };
    case "missing":
      return { key: "noValue", tone: "missing" };
    default:
      return { key: "empty", tone: "muted" };
  }
}

const BADGE_TONE: Record<BadgeTone, { tag: string; icon: string }> = {
  auto: { tag: "bg-primary/10 text-primary", icon: "bg-primary/10 text-primary" },
  doubt: { tag: "bg-warning/12 text-warning", icon: "bg-warning/15 text-warning" },
  missing: {
    tag: "bg-destructive/10 text-destructive",
    icon: "bg-destructive/10 text-destructive",
  },
  user: { tag: "bg-success/12 text-success", icon: "bg-success/12 text-success" },
  progress: { tag: "bg-primary/8 text-primary", icon: "bg-primary/8 text-primary" },
  muted: { tag: "bg-muted text-muted-foreground", icon: "bg-muted text-muted-foreground" },
  mine: { tag: "bg-chart-4/15 text-chart-4", icon: "bg-chart-4/15 text-chart-4" },
};

const BADGE_ICON: Record<TagKey, LucideIcon> = {
  auto: CheckIcon,
  declared: CheckIcon,
  conflict: ArrowLeftRightIcon,
  outdated: CircleAlertIcon,
  unsure: CircleAlertIcon,
  onlyYou: UserIcon,
  noValue: MinusIcon,
  empty: MinusIcon,
  searching: LoaderCircleIcon,
  writing: LoaderCircleIcon,
  kept: CheckIcon,
  entered: PenLineIcon,
  leftEmpty: MinusIcon,
  notSaved: CircleAlertIcon,
  signature: PenLineIcon,
};

function FieldTag({ field }: { field: QueueField }) {
  const t = useTranslations("fieldList.tag");
  const badge = fieldBadge(field);
  return (
    <span
      className={cn(
        "flex-none rounded-[5px] px-1.5 py-0.5 text-[10.5px] font-semibold whitespace-nowrap",
        BADGE_TONE[badge.tone].tag,
      )}
    >
      {t(badge.key, badge.values)}
    </span>
  );
}

function FieldIcon({ field }: { field: QueueField }) {
  const badge = fieldBadge(field);
  const Icon = BADGE_ICON[badge.key];
  return (
    <span
      aria-hidden
      className={cn(
        "grid size-5 flex-none place-items-center rounded-md",
        badge ? BADGE_TONE[badge.tone].icon : "bg-muted",
      )}
    >
      {Icon && <Icon className={cn("size-3", badge?.tone === "progress" && "animate-spin")} />}
    </span>
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
function FieldSources({
  field,
  expanded,
  onOpenSource,
}: {
  field: QueueField;
  expanded: boolean;
  onOpenSource: (fieldId: number, index: number) => void;
}) {
  const t = useTranslations("fieldList");
  const tSource = useTranslations("source");
  const citations = fieldSources(field).map(({ citation }) => citation);
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
          <button
            type="button"
            aria-label={tSource("open", { name: citation.document_name })}
            onClick={(event) => {
              event.stopPropagation();
              onOpenSource(field.id, index);
            }}
            className="text-left font-medium text-primary underline-offset-2 hover:underline"
          >
            <SourceName citation={citation} />
          </button>
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

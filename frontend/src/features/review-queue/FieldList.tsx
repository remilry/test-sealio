"use client";

import { useEffect, useRef, type FormEvent } from "react";
import { PenLineIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/shared/lib/utils";
import type { Schema } from "@/shared/api";
import { Input } from "@/shared/ui/input";
import { formatDate, formatTime } from "@/shared/utils/date";

/** A field as the list shows it: what the user sees and edits, nothing of the file layout. */
export type QueueField = {
  id: number;
  label: string;
  /** Signatures and stamps are shown but never filled. */
  fillable: boolean;
  value: string | null;
  /** What the user typed but could not be saved: kept in the input so they can try again. */
  unsaved: string | null;
  /** When the user entered the value (ISO timestamp); null when it was filled automatically. */
  enteredAt: string | null;
  /** Where the automatic fill is for this field: not reached yet, being searched, answered. */
  state: "pending" | "searching" | "answered";
  /** How sure the answer is (null for the user's own value or no answer). */
  type: Schema<"AnswerOut">["type"];
  resolvedBy: "ai" | "user" | null;
  /** The values found and the quotes supporting them; the selected one is the first. */
  candidates: Schema<"Candidate">[];
  /** Why only the user can fill this field. */
  userOnlyReason: string | null;
};

/** What the status lines name: the bidder and how many documents were searched (when known). */
export type FieldContext = { companyName: string; documentCount: number };

/** Ask the list to move the keyboard focus to a field's input (changes on every request). */
export type FocusRequest = { fieldId: number; at: number };

/**
 * The fields of the form, in order, each with its input. A value is saved when the user leaves
 * the input or presses Enter (which also moves on to the next field). Every keystroke is reported
 * through `onDraft`, so the document can show the text while it is typed.
 */
export function FieldList({
  fields,
  selectedId,
  focusRequest,
  context,
  onSelect,
  onSave,
  onNext,
  onDraft,
}: {
  context: FieldContext | undefined;
  fields: QueueField[];
  selectedId: number | null;
  focusRequest: FocusRequest | null;
  onSelect: (fieldId: number) => void;
  onSave: (fieldId: number, value: string | null) => void;
  onNext: (fieldId: number) => void;
  onDraft: (fieldId: number, text: string) => void;
}) {
  const t = useTranslations("fieldList");
  const inputs = useRef(new Map<number, HTMLInputElement>());

  useEffect(() => {
    if (focusRequest) inputs.current.get(focusRequest.fieldId)?.focus();
  }, [focusRequest]);

  return (
    <ol aria-label={t("label")} className="flex flex-col gap-2">
      {fields.map((field) => (
        <li
          key={field.id}
          aria-label={field.label}
          aria-current={field.id === selectedId ? "true" : undefined}
          onClick={() => onSelect(field.id)}
          className={cn(
            "rounded-lg border bg-card px-3.5 py-3 transition-colors",
            field.id === selectedId && "border-primary ring-3 ring-primary/15",
          )}
        >
          {field.fillable ? (
            <FieldInput
              field={field}
              selected={field.id === selectedId}
              context={context}
              inputRef={(input) => {
                if (input) inputs.current.set(field.id, input);
                else inputs.current.delete(field.id);
              }}
              onFocus={() => onSelect(field.id)}
              onSave={(value) => onSave(field.id, value)}
              onNext={() => onNext(field.id)}
              onDraft={(text) => onDraft(field.id, text)}
            />
          ) : (
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium">{field.label}</span>
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <PenLineIcon className="size-3.5" aria-hidden />
                {t("signByHand")}
              </p>
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}

function FieldInput({
  field,
  selected,
  context,
  inputRef,
  onFocus,
  onSave,
  onNext,
  onDraft,
}: {
  field: QueueField;
  selected: boolean;
  context: FieldContext | undefined;
  inputRef: (input: HTMLInputElement | null) => void;
  onFocus: () => void;
  onSave: (value: string | null) => void;
  onNext: () => void;
  onDraft: (text: string) => void;
}) {
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
    if (value === lastSent.current) return;
    lastSent.current = value;
    onSave(value || null);
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const element = event.currentTarget.elements.namedItem("value");
    if (element instanceof HTMLInputElement) saveIfChanged(element);
    onNext();
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
        autoComplete="off"
        onFocus={onFocus}
        onChange={(event) => onDraft(event.currentTarget.value)}
        onBlur={(event) => saveIfChanged(event.currentTarget)}
      />
      <FieldStatus field={field} context={context} />
      <FieldSources field={field} expanded={selected} />
    </form>
  );
}

/** The line under the input: what the field's value is, or where its search is. */
function FieldStatus({ field, context }: { field: QueueField; context: FieldContext | undefined }) {
  const t = useTranslations("fieldList");
  if (field.unsaved !== null) {
    return <p className="text-xs text-destructive">{t("notSaved")}</p>;
  }
  if (field.state === "searching") {
    return <p className="animate-pulse text-xs text-primary">{t("searching")}</p>;
  }
  if (field.resolvedBy === "user" && field.enteredAt) {
    return (
      <p className="text-xs text-muted-foreground">
        {t("enteredByYou", { time: formatTime(field.enteredAt) })}
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
  return t("source", { document: citation.document_name, page: citation.page });
}

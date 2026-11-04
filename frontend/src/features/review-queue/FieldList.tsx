"use client";

import { useEffect, useRef, type FormEvent } from "react";
import { PenLineIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/shared/lib/utils";
import { Input } from "@/shared/ui/input";
import { formatTime } from "@/shared/utils/date";

/** A field as the list shows it: what the user sees and edits, nothing of the file layout. */
export type QueueField = {
  id: number;
  label: string;
  /** Signatures and stamps are shown but never filled. */
  fillable: boolean;
  value: string | null;
  /** What the user typed but could not be saved: kept in the input so they can try again. */
  unsaved: string | null;
  /** When the user entered the value (ISO timestamp). */
  enteredAt: string | null;
};

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
  onSelect,
  onSave,
  onNext,
  onDraft,
}: {
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
  inputRef,
  onFocus,
  onSave,
  onNext,
  onDraft,
}: {
  field: QueueField;
  inputRef: (input: HTMLInputElement | null) => void;
  onFocus: () => void;
  onSave: (value: string | null) => void;
  onNext: () => void;
  onDraft: (text: string) => void;
}) {
  const t = useTranslations("fieldList");
  const inputId = `field-${field.id}`;
  // The last value sent (or saved), so Enter then leaving the input saves once. Back to the saved
  // value when a save fails, so the kept text is sent again.
  const lastSent = useRef(field.value ?? "");
  useEffect(() => {
    lastSent.current = field.value ?? "";
  }, [field.value, field.unsaved]);
  const saveIfChanged = (input: HTMLInputElement) => {
    const value = input.value.trim();
    if (value === lastSent.current) return;
    lastSent.current = value;
    onSave(value || null);
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const input = event.currentTarget.elements.namedItem("value");
    if (input instanceof HTMLInputElement) saveIfChanged(input);
    onNext();
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium">
        {field.label}
      </label>
      <Input
        // Remounts with the saved value (trimmed by the back) once saved, or with what could not be.
        key={field.unsaved ?? field.value ?? ""}
        ref={inputRef}
        id={inputId}
        name="value"
        defaultValue={field.unsaved ?? field.value ?? ""}
        autoComplete="off"
        onFocus={onFocus}
        onChange={(event) => onDraft(event.currentTarget.value)}
        onBlur={(event) => saveIfChanged(event.currentTarget)}
      />
      {field.unsaved !== null ? (
        <p className="text-xs text-destructive">{t("notSaved")}</p>
      ) : (
        <p className="text-xs text-muted-foreground">
          {field.value && field.enteredAt
            ? t("enteredByYou", { time: formatTime(field.enteredAt) })
            : t("empty")}
        </p>
      )}
    </form>
  );
}

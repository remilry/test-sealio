"use client";

import { useRef, type ReactNode, type RefObject } from "react";
import { LibraryIcon, PlusIcon, TriangleAlertIcon, UploadIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { ApiError } from "@/shared/api";
import { useDraggingFiles } from "@/shared/components/FileDropArea";
import { cn } from "@/shared/lib/utils";
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { ACCEPTED_FILES } from "./knowledge-base.api";
import { useAddDocuments, useDeleteDocument } from "./knowledge-base.queries";

type AddDocuments = ReturnType<typeof useAddDocuments>;

/**
 * The page's file picker (one per page), opened by "Add documents" and by "browse": render
 * `picker` once, pass `browse` to the controls.
 */
export function useDocumentPicker(add: AddDocuments) {
  const input = useRef<HTMLInputElement>(null);
  return {
    picker: <FilePicker inputRef={input} add={add} />,
    browse: () => input.current?.click(),
  };
}

/** "Add documents" in the top bar. */
export function AddDocumentsButton({ add, onBrowse }: { add: AddDocuments; onBrowse: () => void }) {
  const t = useTranslations("knowledge");
  return (
    <Button size="sm" disabled={add.isPending} onClick={onBrowse}>
      <PlusIcon data-icon="inline-start" />
      {add.isPending ? t("adding") : t("addDocuments")}
    </Button>
  );
}

/**
 * Where to drop documents, always shown: a strip below the list, or the whole empty state when
 * there is no document yet. It lights up while files are dragged over the page (the drop itself
 * is handled by the page's `FileDropArea`), and also lets the user browse for files.
 */
export function DocumentDropZone({
  add,
  onBrowse,
  empty,
}: {
  add: AddDocuments;
  onBrowse: () => void;
  empty: boolean;
}) {
  const t = useTranslations("knowledge");
  const dragging = useDraggingFiles();
  const browse = (chunks: ReactNode) => (
    <button
      type="button"
      disabled={add.isPending}
      onClick={onBrowse}
      className="cursor-pointer font-medium text-primary underline-offset-4 hover:underline disabled:cursor-default disabled:opacity-50"
    >
      {chunks}
    </button>
  );

  return (
    <section
      aria-label={t("dropZone")}
      className={cn(
        "flex items-center rounded-xl border-[1.5px] border-dashed text-sm transition-colors",
        dragging ? "border-primary bg-primary/5" : "border-muted-foreground/35 bg-card/60",
        empty ? "flex-col gap-3 px-6 py-14 text-center" : "gap-3 px-4 py-3.5",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "grid place-items-center rounded-lg bg-muted text-muted-foreground",
          dragging && "bg-primary/10 text-primary",
          empty ? "size-10" : "size-8",
        )}
      >
        {empty ? <LibraryIcon className="size-5" /> : <UploadIcon className="size-4" />}
      </span>
      {empty && (
        <div className="flex flex-col gap-1">
          <h2 className="font-medium">{t("noneTitle")}</h2>
          <p className="text-muted-foreground">{t("noneDescription")}</p>
        </div>
      )}
      <div className={cn("flex flex-col gap-0.5", !empty && "flex-1")}>
        {dragging ? (
          <p className="font-medium text-primary">{t("dropRelease")}</p>
        ) : (
          <p>{t.rich("dropHere", { browse })}</p>
        )}
        <p className="text-xs text-muted-foreground">{t("dropFormats")}</p>
      </div>
    </section>
  );
}

/** The hidden file input behind "Add documents" and "browse" (see useDocumentPicker). */
function FilePicker({
  inputRef,
  add,
}: {
  inputRef: RefObject<HTMLInputElement | null>;
  add: AddDocuments;
}) {
  const t = useTranslations("knowledge");
  return (
    <input
      ref={inputRef}
      type="file"
      multiple
      accept={ACCEPTED_FILES}
      aria-label={t("chooseFiles")}
      className="sr-only"
      tabIndex={-1}
      onChange={(event) => {
        const files = Array.from(event.currentTarget.files ?? []);
        // Cleared so choosing the same file again still triggers a change.
        event.currentTarget.value = "";
        if (files.length > 0) add.mutate(files);
      }}
    />
  );
}

/** Why the files could not be added: the back's reason when it refused them, written for users. */
export function AddDocumentsError({ add }: { add: AddDocuments }) {
  const t = useTranslations("knowledge");
  if (!add.error) return null;
  return (
    <Alert variant="destructive">
      <TriangleAlertIcon />
      <AlertTitle>{t("addFailed")}</AlertTitle>
      <AlertDescription>{refusal(add.error) ?? t("addFailedRetry")}</AlertDescription>
      <AlertAction>
        <Button variant="outline" size="sm" onClick={() => add.reset()}>
          {t("dismiss")}
        </Button>
      </AlertAction>
    </Alert>
  );
}

function refusal(error: Error): string | null {
  return error instanceof ApiError && error.status === 422 ? error.message : null;
}

/** A deletion failed: the document is back in the list, and the user is told. */
export function DeleteDocumentError({ remove }: { remove: ReturnType<typeof useDeleteDocument> }) {
  const t = useTranslations("knowledge");
  const tCommon = useTranslations("common");
  if (!remove.error || !remove.variables) return null;
  return (
    <Alert variant="destructive">
      <TriangleAlertIcon />
      <AlertTitle>{t("deleteFailed", { name: remove.variables.name })}</AlertTitle>
      <AlertDescription>{tCommon("retryLater")}</AlertDescription>
      <AlertAction>
        <Button variant="outline" size="sm" onClick={() => remove.reset()}>
          {t("dismiss")}
        </Button>
      </AlertAction>
    </Alert>
  );
}

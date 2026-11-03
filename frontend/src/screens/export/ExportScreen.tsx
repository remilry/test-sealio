"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeftIcon, FileQuestionIcon } from "lucide-react";
import { fillQueries } from "@/features/fill-session";
import { ExportPanel, exportQueries } from "@/features/form-export";
import { isNotFound } from "@/shared/api";
import { routes } from "@/shared/lib/routes";
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button, buttonVariants } from "@/shared/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/shared/ui/empty";
import { Skeleton } from "@/shared/ui/skeleton";

/** Export (docs/USER_FLOW.md §3.5): last check, then the filled file in its original format. */
export function ExportScreen({ formId }: { formId: number }) {
  const form = useQuery(fillQueries.form(formId));
  const summary = useQuery(exportQueries.summary(formId));
  const error = form.error ?? summary.error;

  return (
    <div className="flex min-h-dvh flex-col bg-muted/30">
      <div className="flex h-13 flex-none items-center gap-3 border-b bg-card px-4">
        <Link
          href={routes.fillForm(formId)}
          aria-label="Back to the form"
          className={buttonVariants({ variant: "outline", size: "icon-sm" })}
        >
          <ArrowLeftIcon />
        </Link>
        <span className="text-sm font-medium">Export</span>
      </div>
      <main className="mx-auto flex w-full max-w-2xl flex-col px-8 pt-10 pb-24">
        {form.isPending || summary.isPending ? (
          <div aria-label="Loading export" className="flex flex-col gap-4">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : error ? (
          isNotFound(error) ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <FileQuestionIcon />
                </EmptyMedia>
                <EmptyTitle role="heading" aria-level={1}>
                  Form not found
                </EmptyTitle>
                <EmptyDescription>It may have been withdrawn by the buyer.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <Alert variant="destructive">
              <AlertTitle>We couldn&apos;t prepare the export.</AlertTitle>
              <AlertDescription>Check that the API is running, then try again.</AlertDescription>
              <AlertAction>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    void form.refetch();
                    void summary.refetch();
                  }}
                >
                  Try again
                </Button>
              </AlertAction>
            </Alert>
          )
        ) : (
          form.data &&
          summary.data && (
            <ExportPanel
              formId={formId}
              formTitle={form.data.title}
              summary={summary.data}
              reviewHref={routes.fillForm(formId)}
            />
          )
        )}
      </main>
    </div>
  );
}

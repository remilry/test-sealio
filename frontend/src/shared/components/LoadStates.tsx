import type { ReactNode } from "react";
import { FileQuestionIcon } from "lucide-react";
import { messages } from "@/shared/lib/messages";
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/shared/ui/empty";

/** A screen with nothing to show: what it opens does not exist (any more), or there is none yet. */
export function EmptyState({
  title,
  icon = <FileQuestionIcon />,
  level = 1,
  children,
}: {
  title: string;
  icon?: ReactNode;
  /** 2 when the page already has its h1. */
  level?: 1 | 2;
  children: ReactNode;
}) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">{icon}</EmptyMedia>
        <EmptyTitle role="heading" aria-level={level}>
          {title}
        </EmptyTitle>
        <EmptyDescription>{children}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

/** Loading failed: said in plain words (nothing technical), with a way to try again. */
export function LoadError({ title, onRetry }: { title: string; onRetry: () => void }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{messages.retryLater}</AlertDescription>
      <AlertAction>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      </AlertAction>
    </Alert>
  );
}

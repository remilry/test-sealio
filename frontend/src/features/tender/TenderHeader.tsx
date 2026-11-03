import { Badge } from "@/shared/ui/badge";
import type { TenderDetail } from "./api";
import { formatDeadline } from "./deadline";

export function TenderHeader({ tender }: { tender: TenderDetail }) {
  return (
    <header className="flex flex-wrap items-start gap-4">
      <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-1.5">
        <div className="mb-1 flex gap-1.5">
          <Badge variant="secondary">{tender.procedure}</Badge>
          <Badge variant="secondary">Ref. {tender.reference}</Badge>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">{tender.title}</h1>
        <p className="text-muted-foreground">
          {tender.authority} · {tender.summary}
        </p>
      </div>
      <div
        role="group"
        aria-labelledby="submission-due"
        className="rounded-lg border border-warning/25 bg-warning/5 px-3.5 py-2.5 text-right"
      >
        <div id="submission-due" className="text-xs font-medium text-warning">
          Submission due
        </div>
        <div className="text-base font-semibold tracking-tight">
          {formatDeadline(tender.submission_deadline)}
        </div>
      </div>
    </header>
  );
}

import Link from "next/link";
import { useTranslations } from "next-intl";
import { routes } from "@/shared/lib/routes";
import { Card } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { useKnowledgeBase } from "./knowledge-base.queries";

/** Tender page summary: what the AI answers from, and a link to manage it. */
export function KnowledgeCard() {
  const t = useTranslations("knowledge");
  return (
    <section aria-labelledby="knowledge-card-title">
      <Card className="gap-3 px-4 py-4">
        <div className="flex items-baseline justify-between gap-4">
          <h2 id="knowledge-card-title" className="font-semibold">
            {t("cardTitle")}
          </h2>
          <Link
            href={routes.knowledge}
            className="text-xs font-medium text-primary hover:underline"
          >
            {t("manage")}
          </Link>
        </div>
        <p className="-mt-2 text-xs text-muted-foreground">{t("cardHint")}</p>
        <DocumentCount />
      </Card>
    </section>
  );
}

function DocumentCount() {
  const t = useTranslations("knowledge");
  const { data: knowledge, isPending } = useKnowledgeBase();
  if (isPending) return <Skeleton className="h-10 w-20" />;
  if (!knowledge) return <p className="text-xs text-muted-foreground">{t("cardUnavailable")}</p>;
  const count = knowledge.documents.length;
  return (
    <div>
      <div className="text-xl font-semibold tracking-tight">{count}</div>
      <div className="text-xs text-muted-foreground">{t("cardDocuments", { count })}</div>
    </div>
  );
}

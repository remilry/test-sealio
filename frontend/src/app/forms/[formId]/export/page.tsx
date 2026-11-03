import { Suspense } from "react";
import { ExportScreen } from "@/screens/export";

export default function ExportFormPage({ params }: PageProps<"/forms/[formId]/export">) {
  return (
    <Suspense fallback={null}>
      {params.then(({ formId }) => (
        <ExportScreen formId={Number(formId)} />
      ))}
    </Suspense>
  );
}

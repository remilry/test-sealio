import { Suspense } from "react";
import { LiveFillScreen } from "@/screens/live-fill";

// Full screen, outside the shell. The form id is only known at request time (Cache Components).
export default function FillFormPage({ params }: PageProps<"/forms/[formId]/fill">) {
  return (
    <Suspense fallback={null}>
      {params.then(({ formId }) => (
        <LiveFillScreen formId={Number(formId)} />
      ))}
    </Suspense>
  );
}

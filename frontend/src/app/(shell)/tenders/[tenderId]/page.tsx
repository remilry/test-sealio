import { Suspense } from "react";
import { TenderScreen } from "@/screens/tender";

// The tender id is only known at request time: resolve it inside Suspense (Cache Components).
export default function TenderPage({ params }: PageProps<"/tenders/[tenderId]">) {
  return (
    <Suspense fallback={null}>
      {params.then(({ tenderId }) => (
        <TenderScreen tenderId={Number(tenderId)} />
      ))}
    </Suspense>
  );
}

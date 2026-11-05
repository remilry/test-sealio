"use client";

import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { DevTools } from "@/screens/dev-tools";
import { getQueryClient } from "@/shared/api/query-client";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={getQueryClient()}>
      {children}
      <DevTools />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}

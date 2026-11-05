import type { ReactElement, ReactNode } from "react";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { defaultLocale, timeZone } from "@/shared/i18n/config";
import messages from "@/shared/i18n/messages/en.json";

/**
 * Renders a screen as the app does: English messages, and a fresh TanStack Query cache (no
 * retries, so errors show up immediately).
 */
export function renderScreen(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } },
  });
  // As a wrapper, so `rerender` keeps the same providers and cache.
  const wrapper = ({ children }: { children: ReactNode }) => (
    <NextIntlClientProvider locale={defaultLocale} timeZone={timeZone} messages={messages}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </NextIntlClientProvider>
  );
  return { queryClient, ...render(ui, { wrapper }) };
}

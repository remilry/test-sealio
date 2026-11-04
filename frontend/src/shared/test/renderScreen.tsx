import type { ReactElement } from "react";
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
  return {
    queryClient,
    ...render(
      <NextIntlClientProvider locale={defaultLocale} timeZone={timeZone} messages={messages}>
        <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
      </NextIntlClientProvider>,
    ),
  };
}

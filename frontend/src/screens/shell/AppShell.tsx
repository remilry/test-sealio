"use client";

import { Suspense, type ReactNode } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { ActiveTenders } from "@/features/tender";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarProvider,
} from "@/shared/ui/sidebar";

// Demo account (no login yet): data, not interface text. Will come from the session.
const ACCOUNT = {
  company: "Alpenlogic AG",
  user: { name: "Marc Keller", role: "Head of Bids" },
};

/** "Alpenlogic AG" → "AL", "Marc Keller" → "MK" */
function initials(name: string, single = false) {
  const words = name.split(/\s+/).filter(Boolean);
  if (single || words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

/**
 * Sidebar + content for the Tender and Company knowledge screens (Live fill is full screen).
 * Company knowledge appears in the nav once that screen exists (no dead links).
 */
export function AppShell({ children }: { children: ReactNode }) {
  const t = useTranslations("shell");
  const tCommon = useTranslations("common");
  const appName = tCommon("appName");
  return (
    <SidebarProvider>
      <Sidebar>
        <SidebarHeader className="gap-4">
          <Link href="/" className="flex items-center gap-2 px-2 pt-1">
            <span className="grid size-6 place-items-center rounded-md bg-foreground text-xs font-bold text-background">
              {appName.charAt(0)}
            </span>
            <span className="text-[14.5px] font-semibold tracking-tight">{appName}</span>
          </Link>
          <div className="flex items-center gap-2 rounded-lg border bg-card px-2 py-1.5">
            <span className="grid size-5 place-items-center rounded bg-primary/15 text-[9.5px] font-bold text-primary">
              {initials(ACCOUNT.company, true)}
            </span>
            <span className="font-medium">{ACCOUNT.company}</span>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarMenu aria-label={t("mainNav")}>
              <SidebarMenuItem>
                <SidebarMenuButton isActive render={<Link href="/" />}>
                  {t("tenders")}
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroup>
          {/* usePathname suspends on dynamic routes with Cache Components: keep it in a boundary. */}
          <Suspense fallback={<SidebarMenuSkeleton />}>
            <ActiveTenders />
          </Suspense>
        </SidebarContent>
        <SidebarFooter>
          <div className="flex items-center gap-2 border-t px-2 pt-2.5">
            <span className="grid size-7 place-items-center rounded-full bg-primary/15 text-[11px] font-semibold text-primary">
              {initials(ACCOUNT.user.name)}
            </span>
            <div className="leading-tight">
              <div className="font-medium">{ACCOUNT.user.name}</div>
              <div className="text-xs text-muted-foreground">{ACCOUNT.user.role}</div>
            </div>
          </div>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset>{children}</SidebarInset>
    </SidebarProvider>
  );
}

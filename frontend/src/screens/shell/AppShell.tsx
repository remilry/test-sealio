"use client";

import { Suspense, type ReactNode } from "react";
import Link from "next/link";
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

/**
 * Sidebar + content for the Tender and Company knowledge screens (Live fill is full screen).
 * Company knowledge appears in the nav once that screen exists (no dead links).
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <SidebarProvider>
      <Sidebar>
        <SidebarHeader className="gap-4">
          <Link href="/" className="flex items-center gap-2 px-2 pt-1">
            <span className="grid size-6 place-items-center rounded-md bg-foreground text-xs font-bold text-background">
              F
            </span>
            <span className="text-[14.5px] font-semibold tracking-tight">Formpilot</span>
          </Link>
          <div className="flex items-center gap-2 rounded-lg border bg-card px-2 py-1.5">
            <span className="grid size-5 place-items-center rounded bg-primary/15 text-[9.5px] font-bold text-primary">
              AL
            </span>
            <span className="font-medium">Alpenlogic AG</span>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarMenu aria-label="Main">
              <SidebarMenuItem>
                <SidebarMenuButton isActive render={<Link href="/" />}>
                  Tenders
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
              MK
            </span>
            <div className="leading-tight">
              <div className="font-medium">Marc Keller</div>
              <div className="text-xs text-muted-foreground">Head of Bids</div>
            </div>
          </div>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset>{children}</SidebarInset>
    </SidebarProvider>
  );
}
